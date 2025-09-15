import flet as ft
import sqlite3
from datetime import datetime
import uuid
import threading
import time
import os
import shutil
import random
import string
import pyautogui

# ---- simple DB shim (igual ao seu) ----
class db:
    @staticmethod
    def init_db():
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS tabs
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)""")
        c.execute("""CREATE TABLE IF NOT EXISTS tasks
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          tab_name TEXT, 
                          title TEXT,
                          task TEXT, 
                          start_date TEXT, 
                          end_date TEXT, 
                          status TEXT,
                          priority TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS attachments
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          task_id INTEGER, 
                          file_path TEXT,
                          FOREIGN KEY(task_id) REFERENCES tasks(id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings
                         (key TEXT PRIMARY KEY, value TEXT)""")
        conn.commit()
        conn.close()
        if not os.path.exists('attachments'):
            os.makedirs('attachments')

    @staticmethod
    def add_tab(name):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO tabs (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()

    @staticmethod
    def list_tabs():
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("SELECT name FROM tabs")
        tabs = [row[0] for row in c.fetchall()]
        conn.close()
        return tabs

    @staticmethod
    def update_tab_name(old_name, new_name):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("UPDATE tabs SET name = ? WHERE name = ?", (new_name, old_name))
        c.execute("UPDATE tasks SET tab_name = ? WHERE tab_name = ?", (new_name, old_name))
        conn.commit()
        conn.close()

    @staticmethod
    def add_task(tab_name, title, task, start_date, end_date, status, priority):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("INSERT INTO tasks (tab_name, title, task, start_date, end_date, status, priority) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (tab_name, title, task, start_date, end_date, status, priority))
        task_id = c.lastrowid
        conn.commit()
        conn.close()
        return task_id

    @staticmethod
    def list_tasks(tab_name):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("SELECT id, title, task, start_date, end_date, status, priority FROM tasks WHERE tab_name = ?", (tab_name,))
        tasks = []
        for row in c.fetchall():
            tasks.append({
                "id": row[0],
                "title": row[1],
                "task": row[2],
                "start_date": row[3],
                "end_date": row[4],
                "status": row[5],
                "priority": row[6]
            })
        conn.close()
        return tasks

    @staticmethod
    def update_task(task_id, title, task, start_date, end_date, status, priority, tab_name):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("UPDATE tasks SET title = ?, task = ?, start_date = ?, end_date = ?, status = ?, priority = ?, tab_name = ? WHERE id = ?",
                  (title, task, start_date, end_date, status, priority, tab_name, task_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_task(task_id):
        task_attachment_dir = os.path.join('attachments', str(task_id))
        if os.path.exists(task_attachment_dir):
            shutil.rmtree(task_attachment_dir)

        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("DELETE FROM attachments WHERE task_id = ?", (task_id,))
        c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_tab(tab_name):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("SELECT id FROM tasks WHERE tab_name = ?", (tab_name,))
        task_ids = [row[0] for row in c.fetchall()]
        for task_id in task_ids:
            db.delete_task(task_id)
        c.execute("DELETE FROM tabs WHERE name = ?", (tab_name,))
        conn.commit()
        conn.close()

    @staticmethod
    def add_attachment(task_id, file_path):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("INSERT INTO attachments (task_id, file_path) VALUES (?, ?)", (task_id, file_path))
        conn.commit()
        conn.close()

    @staticmethod
    def list_attachments(task_id):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("SELECT id, file_path FROM attachments WHERE task_id = ?", (task_id,))
        attachments = [{"id": row[0], "file_path": row[1]} for row in c.fetchall()]
        conn.close()
        return attachments

    @staticmethod
    def get_attachment(attachment_id):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("SELECT file_path FROM attachments WHERE id = ?", (attachment_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

    @staticmethod
    def delete_attachment(attachment_id):
        file_path = db.get_attachment(attachment_id)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_setting(key, default=None):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = c.fetchone()
        conn.close()
        if result:
            return result[0]
        return default

    @staticmethod
    def set_setting(key, value):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()

# ---- TaskRow - com drag and drop para arquivos e minimização ----
class TaskRow(ft.Container):
    months = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }

    def __init__(self, on_save, on_delete, on_move_up, on_move_down, title=None, task=None, start_date=None, end_date=None, status=None, priority=None, db_id=None, get_auto_save_setting=None, scale=None):
        self.on_save = on_save
        self.on_delete = on_delete
        self.db_id = db_id
        self.is_minimized = False

        self.has_changes = False
        self.is_saving = False
        self.on_move_up = on_move_up
        self.on_move_down = on_move_down
        self.has_date_error = False
        self.attachments_changed = False
        self.original_bgcolor = "#2C2F48"
        self.get_auto_save_setting = get_auto_save_setting
        self.auto_save_timer = None
        self.scale = scale if scale else lambda x: x # Fallback for safety

        self.original_data = {
            "title": title or "",
            "task": task or "",
            "start_date": start_date or "",
            "end_date": end_date or "",
            "status": status or "Ongoing",
            "priority": priority or "Normal"
        }

        self.display_id_text = ft.Text(
            f"#{db_id}" if db_id else "",
            size=self.scale(30),
            color=ft.Colors.GREY_500,
            weight=ft.FontWeight.BOLD,
            visible=db_id is not None
        )

        self.title_field = ft.TextField(
            value=title or "",
            label="Title",
            expand=True,
            border=ft.InputBorder.UNDERLINE,
            text_style=ft.TextStyle(size=self.scale(16), weight=ft.FontWeight.BOLD),
            content_padding=ft.padding.symmetric(vertical=self.scale(15), horizontal=self.scale(10)),
            on_change=self._on_field_change
        )

        self.task_field = ft.TextField(
            value=task or "",
            label="Task",
            multiline=True,
            min_lines=2,
            max_lines=6,
            expand=True,
            text_style=ft.TextStyle(size=self.scale(12)),
            content_padding=ft.padding.symmetric(vertical=self.scale(20), horizontal=self.scale(10)),
            on_change=self._on_field_change
        )

        self.attachments_list = ft.Column(spacing=self.scale(5))
        self.progress_bar = ft.ProgressBar(visible=False, height=self.scale(10))

        self.drop_zone = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.UPLOAD_FILE, size=40),
                    ft.Text("Drop files here to attach"),
                    self.progress_bar,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            alignment=ft.alignment.center,
            border=ft.border.all(color=ft.Colors.PRIMARY, width=2),
            border_radius=10,
            padding=self.scale(20),
            visible=False,
            margin=ft.margin.symmetric(vertical=self.scale(10)),
        )

        self.start_date_picker = ft.DatePicker(
            on_change=self._on_start_date_change,
            on_dismiss=self._on_picker_dismiss,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31),
        )
        self.end_date_picker = ft.DatePicker(
            on_change=self._on_end_date_change,
            on_dismiss=self._on_picker_dismiss,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31),
        )

        self.file_picker = ft.FilePicker(on_result=self._on_file_picker_result)

        self.start_date_field = ft.TextField(
            value=start_date or "",
            label="Start date",
            width=self.scale(150),
            read_only=True,
            border=ft.InputBorder.UNDERLINE,
            content_padding=ft.padding.symmetric(vertical=self.scale(15), horizontal=self.scale(10)),
            text_style=ft.TextStyle(size=self.scale(12)),
            suffix=ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                on_click=self._open_start_date_picker
            )
        )
        self.end_date_field = ft.TextField(
            value=end_date or "",
            label="End date",
            width=self.scale(150),
            read_only=True,
            border=ft.InputBorder.UNDERLINE,
            content_padding=ft.padding.symmetric(vertical=self.scale(15), horizontal=self.scale(10)),
            text_style=ft.TextStyle(size=self.scale(12)),
            suffix=ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                on_click=self._open_end_date_picker
            )
        )

        self.status_field = ft.Dropdown(
            options=[ft.dropdown.Option("Ongoing"), ft.dropdown.Option("Complete")],
            value=status or "Ongoing",
            width=self.scale(150),
            border=ft.InputBorder.UNDERLINE,
            border_radius=0,
            text_style=ft.TextStyle(size=self.scale(12)),
            content_padding=ft.padding.symmetric(vertical=self.scale(15), horizontal=self.scale(10)),
            on_change=self._on_status_dropdown_change
        )

        self.priority_field = ft.Dropdown(
            options=[
                ft.dropdown.Option("Not Urgent"),
                ft.dropdown.Option("Normal"),
                ft.dropdown.Option("Critical")
            ],
            value=priority or "Normal",
            width=self.scale(150),
            border=ft.InputBorder.UNDERLINE,
            border_radius=0,
            text_style=ft.TextStyle(size=self.scale(12)),
            content_padding=ft.padding.symmetric(vertical=self.scale(15), horizontal=self.scale(10)),
            on_change=self._on_field_change
        )

        self.change_indicator = ft.Icon(ft.Icons.EDIT, color=ft.Colors.ORANGE, size=self.scale(20), visible=False)
        self.save_indicator = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=self.scale(20), visible=False)
        self.date_error_indicator = ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED, size=self.scale(20), visible=False)

        self.date_error_text = ft.Text("Start date cannot be after end date", color=ft.Colors.RED, size=self.scale(12), visible=False)

        self.save_btn = ft.IconButton(icon=ft.Icons.SAVE, tooltip="Save", on_click=self.save)
        self.delete_btn = ft.IconButton(icon=ft.Icons.DELETE, tooltip="Delete", on_click=self.delete)
        self.attach_btn = ft.IconButton(icon=ft.Icons.ATTACH_FILE, tooltip="Attach files", on_click=self._attach_file, disabled=self.db_id is None)
        self.move_up_btn = ft.IconButton(icon=ft.Icons.ARROW_UPWARD, on_click=self._move_up, visible=False, tooltip="Move up")
        self.move_down_btn = ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD, on_click=self._move_down, visible=False, tooltip="Move down")
        self.minimize_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP, 
            tooltip="Minimize", 
            on_click=self._toggle_minimize
        )

        self.reorder_arrows_col = ft.Column([self.move_up_btn, self.move_down_btn], spacing=0)

        # Cabeçalho da task com botão de minimizar
        self.task_header = ft.Row([
            self.display_id_text,
            self.title_field,
            self.minimize_btn
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Conteúdo expandível da task
        indicators_row = ft.Row([self.change_indicator, self.save_indicator, self.date_error_indicator], spacing=self.scale(5))
        status_row = ft.Row([self.start_date_field, self.end_date_field], spacing=self.scale(12))
        priority_status_row = ft.Row([self.priority_field, self.status_field, ft.Container(expand=True), indicators_row, self.attach_btn, self.save_btn, self.delete_btn], spacing=self.scale(12))

        self.expandable_content = ft.Column([
            self.task_field, 
            self.drop_zone, 
            self.attachments_list, 
            status_row, 
            self.date_error_text, 
            priority_status_row
        ], spacing=self.scale(12))

        # Conteúdo minimizado - apenas informações essenciais
        self.attachment_count = 0
        self.minimized_dates_text = ft.Text("", size=self.scale(12), color=ft.Colors.GREY_400)
        self.minimized_attachments_text = ft.Text("", size=self.scale(12), color=ft.Colors.BLUE_400)
        self.minimized_due_date_info = ft.Row(
            [
                ft.Icon(ft.Icons.ALARM, size=self.scale(12)),
                ft.Text("", size=self.scale(12), weight=ft.FontWeight.BOLD)
            ],
            visible=False,
            spacing=self.scale(4),
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        self.minimized_info = ft.Row([
            self.minimized_dates_text,
            self.minimized_attachments_text,
            self.minimized_due_date_info,
        ], spacing=self.scale(10), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.task_main_content = ft.Column([
            self.task_header,
            self.expandable_content,
            self.minimized_info
        ], spacing=self.scale(12), expand=True)

        # Container principal da task
        self.main_container = ft.Container(
            content=ft.Row(
                [self.reorder_arrows_col, self.task_main_content],
                vertical_alignment=ft.CrossAxisAlignment.START
            ),
            padding=self.scale(20),
            bgcolor=self.original_bgcolor,
            border_radius=self.scale(20),
            margin=ft.margin.only(bottom=self.scale(10))
        )

        # Wrap in a file drop target
        super().__init__(
            content=ft.DragTarget(
                group="files",
                content=self.main_container,
                on_will_accept=self._on_drag_will_accept,
                on_accept=self._on_drag_accept,
                on_leave=self._on_drag_leave,
            )
        )

        if self.db_id:
            self._load_attachments()
        self._on_status_change()
        self._validate_dates()
        self._update_minimized_info()
        self.set_minimized(True)

    def _move_up(self, e):
        if self.on_move_up:
            self.on_move_up(self)

    def _move_down(self, e):
        if self.on_move_down:
            self.on_move_down(self)

    def _toggle_minimize(self, e):
        self.set_minimized(not self.is_minimized)

    def set_minimized(self, minimized: bool):
        self.is_minimized = minimized
        if self.is_minimized:
            # Minimizar
            self.expandable_content.visible = False
            self.minimized_info.visible = True
            self.minimize_btn.icon = ft.Icons.KEYBOARD_ARROW_DOWN
            self.minimize_btn.tooltip = "Maximize"
        else:
            # Maximizar
            self.expandable_content.visible = True
            self.minimized_info.visible = False
            self.minimize_btn.icon = ft.Icons.KEYBOARD_ARROW_UP
            self.minimize_btn.tooltip = "Minimize"
        try:
            self.update()
        except:
            pass

    def set_reorder_mode(self, active: bool):
        self.move_up_btn.visible = active
        self.move_down_btn.visible = active
        try:
            self.update()
        except:
            pass

    def _update_minimized_info(self):
        # Atualizar informações do modo minimizado
        dates_text = ""
        if self.start_date_field.value and self.end_date_field.value:
            dates_text = f"{self.start_date_field.value} - {self.end_date_field.value}"
        elif self.start_date_field.value:
            dates_text = f"From: {self.start_date_field.value}"
        elif self.end_date_field.value:
            dates_text = f"Until: {self.end_date_field.value}"
        
        attachments_text = ""
        if self.attachment_count > 0:
            attachments_text = f"📎 {self.attachment_count} file{'s' if self.attachment_count > 1 else ''}"
        
        self.minimized_dates_text.value = dates_text
        self.minimized_attachments_text.value = attachments_text

    def _on_drag_will_accept(self, e):
        """Chamado quando um arquivo está sendo arrastado sobre a task"""
        # Verificar se é um arquivo sendo arrastado (data será "true" se aceitar)
        self.main_container.border = ft.border.all(3, ft.Colors.GREEN)
        self.main_container.update()
        return True

    def _on_drag_leave(self, e):
        """Chamado quando o arquivo sai de cima da task"""
        self.main_container.border = None
        self.main_container.update()

    def _on_drag_accept(self, e):
        """Chamado quando um arquivo é solto na task"""
        self.main_container.border = None
        self.main_container.update()
        
        # Mostrar zona de drop temporariamente
        self.drop_zone.visible = True
        self.progress_bar.visible = True
        self.update()
        
        # Simular processamento (já que não temos acesso aos arquivos reais)
        def process_files():
            time.sleep(0.5)  # Simular processamento
            self.progress_bar.visible = False
            self.drop_zone.visible = False
            
            # Simular adição de arquivo
            if self.db_id:
                # Em uma implementação real, você processaria os arquivos aqui
                fake_file_name = f"dropped_file_{random.randint(1000, 9999)}.txt"
                task_attachment_dir = os.path.join('attachments', str(self.db_id))
                if not os.path.exists(task_attachment_dir):
                    os.makedirs(task_attachment_dir)
                
                fake_file_path = os.path.join(task_attachment_dir, fake_file_name)
                # Criar arquivo simulado
                with open(fake_file_path, 'w') as f:
                    f.write("Arquivo simulado adicionado via drag and drop")
                
                db.add_attachment(self.db_id, fake_file_path)
                self._load_attachments()
                
                if hasattr(self, 'page') and self.page:
                    self.page.snack_bar = ft.SnackBar(ft.Text("File attached successfully!"), bgcolor=ft.Colors.GREEN_400)
                    self.page.snack_bar.open = True
                    self.page.update()
            else:
                if hasattr(self, 'page') and self.page:
                    self.page.snack_bar = ft.SnackBar(ft.Text("Please save the task before attaching files."), bgcolor=ft.Colors.ORANGE_400)
                    self.page.snack_bar.open = True
                    self.page.update()
            
            self.update()
        
        threading.Thread(target=process_files, daemon=True).start()

    def handle_dropped_files(self, files):
        self.drop_zone.visible = True
        self.progress_bar.visible = True
        try: self.update()
        except: pass

        if not self.db_id:
            if hasattr(self, 'page') and self.page:
                self.page.snack_bar = ft.SnackBar(ft.Text("Please save the task before attaching files."), bgcolor=ft.Colors.ORANGE_400)
                self.page.snack_bar.open = True
                self.page.update()
            self.hide_drop_zone()
            self.progress_bar.visible = False
            return

        task_attachment_dir = os.path.join('attachments', str(self.db_id))
        if not os.path.exists(task_attachment_dir):
            os.makedirs(task_attachment_dir)

        existing_attachments = db.list_attachments(self.db_id)
        existing_filenames = {os.path.basename(att['file_path']) for att in existing_attachments}

        total_files = len(files)
        attached_count = 0
        skipped_files = []
        for i, f in enumerate(files):
            try:
                self.progress_bar.value = (i + 1) / total_files
                try: self.update()
                except: pass
                if f.name in existing_filenames:
                    skipped_files.append(f.name)
                    continue
                dest_path = os.path.join(task_attachment_dir, f.name)
                shutil.copy(f.path, dest_path)
                db.add_attachment(self.db_id, dest_path)
                attached_count += 1
            except Exception as ex:
                print("attach error:", ex)

        time.sleep(0.1)
        self.progress_bar.visible = False
        self.progress_bar.value = 0
        self.drop_zone.visible = False
        self._load_attachments()
        if hasattr(self, 'page') and self.page:
            if skipped_files:
                skipped_str = ", ".join(skipped_files)
                self.page.snack_bar = ft.SnackBar(ft.Text(f"File(s) already in list: {skipped_str}"), bgcolor=ft.Colors.ORANGE_400)
                self.page.snack_bar.open = True
                self.page.update()
            if attached_count > 0:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"{attached_count} file(s) attached."), bgcolor=ft.Colors.GREEN_400)
                self.page.snack_bar.open = True
                self.page.update()
        if attached_count > 0:
            self.attachments_changed = True
            self._on_field_change()

    def show_drop_zone(self):
        self.drop_zone.visible = True
        try: self.update()
        except: pass

    def hide_drop_zone(self):
        self.drop_zone.visible = False
        try: self.update()
        except: pass

    def _parse_date(self, date_str):
        if not date_str:
            return None
        try:
            parts = date_str.split('/')
            if len(parts) != 3: return None
            day = int(parts[0]); month_name = parts[1]; year = int(parts[2])
            month_names = {v: k for k, v in self.months.items()}
            month = month_names.get(month_name)
            if not month: return None
            return datetime(year, month, day)
        except Exception:
            return None

    def _validate_dates(self):
        start_date = self._parse_date(self.start_date_field.value)
        end_date = self._parse_date(self.end_date_field.value)
        if not start_date or not end_date:
            self._clear_date_error(); return True
        if start_date > end_date:
            self._show_date_error(); return False
        self._clear_date_error(); return True

    def _show_date_error(self):
        self.has_date_error = True
        self.date_error_indicator.visible = True
        self.date_error_text.visible = True
        self.save_btn.disabled = True
        self.start_date_field.border_color = ft.Colors.RED
        self.end_date_field.border_color = ft.Colors.RED
        try: self.update()
        except: pass

    def _clear_date_error(self):
        self.has_date_error = False
        self.date_error_indicator.visible = False
        self.date_error_text.visible = False
        self.save_btn.disabled = False
        self.start_date_field.border_color = None
        self.end_date_field.border_color = None
        try: self.update()
        except: pass

    def _on_field_change(self, e=None):
        if self.auto_save_timer:
            self.auto_save_timer.cancel()

        if self._validate_dates() and self._has_data_changed():
            self._show_change_indicator()
        self._update_minimized_info()

        if self.get_auto_save_setting and self.get_auto_save_setting() and self._has_data_changed() and not self.has_date_error:
            self.auto_save_timer = threading.Timer(1.5, self.save)
            self.auto_save_timer.start()

    def _on_status_dropdown_change(self, e=None):
        self._on_status_change()
        self._on_field_change()
        if hasattr(self.page, 'app_instance'):
            self.page.app_instance.check_all_due_dates()

    def _has_data_changed(self):
        current_data = self.get_data()
        for k, v in current_data.items():
            if str(v) != str(self.original_data.get(k, "")):
                return True
        return self.attachments_changed

    def _show_change_indicator(self):
        self.has_changes = True
        self.change_indicator.visible = True
        self.save_indicator.visible = False
        try: self.update()
        except: pass

    def _hide_change_indicator(self):
        self.has_changes = False
        self.change_indicator.visible = False
        try: self.update()
        except: pass

    def _show_save_indicator(self):
        self.save_indicator.visible = True
        self.change_indicator.visible = False
        try: self.update()
        except: pass
        def hide_after():
            time.sleep(2)
            try:
                self.save_indicator.visible = False
                self.update()
            except: pass
        threading.Thread(target=hide_after, daemon=True).start()

    def _update_original_data(self):
        self.original_data = self.get_data().copy()

    def _load_attachments(self):
        self.attachments_list.controls.clear()
        if not self.db_id:
            self.attachment_count = 0
            self._update_minimized_info()
            try: self.update()
            except: pass
            return
        
        attachments = db.list_attachments(self.db_id)
        self.attachment_count = len(attachments)
        
        for att in attachments:
            file_path = att['file_path']; file_name = os.path.basename(file_path)
            self.attachments_list.controls.append(
                ft.Row([
                    ft.IconButton(icon=ft.Icons.OPEN_IN_NEW, tooltip=f"Open {file_path}", on_click=lambda e, p=file_path: self._open_attachment(p)),
                    ft.Text(file_name, tooltip=file_path, expand=True),
                    ft.IconButton(icon=ft.Icons.DELETE, icon_size=16, tooltip="Delete attachment", on_click=lambda e, att_id=att['id']: self._delete_attachment(att_id))
                ])
            )
        
        self._update_minimized_info()
        try: self.update()
        except: pass

    def _open_attachment(self, path):
        try:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                os.startfile(abs_path)
            else:
                if hasattr(self, 'page') and self.page:
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"File not found: {abs_path}"), bgcolor=ft.Colors.RED_400)
                    self.page.snack_bar.open = True
                    self.page.update()
        except Exception as ex:
            if hasattr(self, 'page') and self.page:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Error opening file: {ex}"), bgcolor=ft.Colors.RED_400)
                self.page.snack_bar.open = True
                self.page.update()

    def _delete_attachment(self, attachment_id):
        db.delete_attachment(attachment_id)
        self._load_attachments()
        self.attachments_changed = True
        self._on_field_change()

    def _attach_file(self, e):
        print(f"[{datetime.now()}] INFO: Opening file picker for task ID: {self.db_id} (Title: '{self.title_field.value}')")
        if hasattr(self, 'page') and self.page:
            self.page.is_file_picker_open = True
        self.file_picker.pick_files(allow_multiple=True)

    def _on_file_picker_result(self, e):
        if hasattr(self, 'page') and self.page:
            self.page.is_file_picker_open = False

        if e.files:
            self.handle_dropped_files(e.files)

    def focus_and_expand(self):
        self.set_minimized(False)
        self.scroll_to(duration=1000, curve=ft.AnimationCurve.EASE_IN_OUT)

    def _get_due_color(self, days_diff):
        if days_diff < 0:
            return ft.Colors.RED_400
        if days_diff > 3:
            return ft.Colors.ORANGE_400

        orange = (255, 167, 38)  # ORANGE_400
        red = (239, 83, 80)      # RED_400
        
        factor = (3 - days_diff) / 3.0
        
        r = int(orange[0] + (red[0] - orange[0]) * factor)
        g = int(orange[1] + (red[1] - orange[1]) * factor)
        b = int(orange[2] + (red[2] - orange[2]) * factor)
        
        return f"#{r:02x}{g:02x}{b:02x}"

    def set_notification_status(self, status, days_diff=None):
        if status == "overdue":
            self.main_container.bgcolor = "#4d2626"  # Dark red tint
            self.minimized_due_date_info.visible = True
            color = ft.Colors.RED_400
            self.minimized_due_date_info.controls[0].color = color
            self.minimized_due_date_info.controls[1].value = f"{-days_diff}d overdue"
            self.minimized_due_date_info.controls[1].color = color
        elif status == "upcoming":
            self.main_container.bgcolor = "#4d3d26"  # Dark orange tint
            self.minimized_due_date_info.visible = True
            color = self._get_due_color(days_diff)
            self.minimized_due_date_info.controls[0].color = color
            self.minimized_due_date_info.controls[1].value = f"in {days_diff}d"
            self.minimized_due_date_info.controls[1].color = color
        else:  # None
            self.main_container.bgcolor = self.original_bgcolor
            self.minimized_due_date_info.visible = False
        
        try: self.update()
        except: pass

    def did_mount(self):
        if hasattr(self, 'page') and self.page:
            try:
                self.page.overlay.append(self.start_date_picker)
                self.page.overlay.append(self.end_date_picker)
                self.page.overlay.append(self.file_picker)
                self.page.update()
            except: pass

    def will_unmount(self):
        if hasattr(self, 'page') and self.page:
            try:
                self.page.overlay.remove(self.start_date_picker)
                self.page.overlay.remove(self.end_date_picker)
                self.page.overlay.remove(self.file_picker)
                self.page.update()
            except: pass

    def _format_date(self, date_obj):
        if not date_obj: return ""
        day = date_obj.day; month = self.months.get(date_obj.month, "Inv"); year = date_obj.year
        return f"{day:02d}/{month}/{year}"

    def _open_start_date_picker(self, e):
        end_date = self._parse_date(self.end_date_field.value)
        if end_date:
            self.start_date_picker.last_date = end_date
        else:
            # Reset if no end date is set
            self.start_date_picker.last_date = datetime(2030, 12, 31)
        self.page.is_picker_open = True
        self.page.open(self.start_date_picker)

    def _open_end_date_picker(self, e):
        start_date = self._parse_date(self.start_date_field.value)
        if start_date:
            self.end_date_picker.first_date = start_date
        else:
            # Reset if no start date is set
            self.end_date_picker.first_date = datetime(2020, 1, 1)
        self.page.is_picker_open = True
        self.page.open(self.end_date_picker)

    def _on_picker_dismiss(self, e):
        self.page.is_picker_open = False

    def _on_start_date_change(self, e):
        self.page.is_picker_open = False
        selected_date = e.control.value
        self.start_date_field.value = self._format_date(selected_date)        
        if selected_date:
            self.end_date_picker.first_date = selected_date
            current_end_date = self._parse_date(self.end_date_field.value)
            if current_end_date and current_end_date < selected_date:
                self.end_date_field.value = ""
                try: self.end_date_field.update()
                except: pass

        self.start_date_picker.open = False
        self.start_date_field.update()
        self.page.update()
        self._on_field_change()

    def _on_end_date_change(self, e):
        self.page.is_picker_open = False
        selected_date = e.control.value
        self.end_date_field.value = self._format_date(selected_date)

        if selected_date:
            self.start_date_picker.last_date = selected_date
            current_start_date = self._parse_date(self.start_date_field.value)
            if current_start_date and current_start_date > selected_date:
                self.start_date_field.value = ""
                try: self.start_date_field.update()
                except: pass

        self.end_date_picker.open = False
        self.end_date_field.update()
        self.page.update()
        self._on_field_change()
        if hasattr(self.page, 'app_instance'):
            self.page.app_instance.check_all_due_dates()

    def _on_status_change(self, e=None):
        v = (self.status_field.value or "").lower()
        if v == "ongoing": self.status_field.color = "#FFA726"
        elif v == "complete": self.status_field.color = "#66BB6A"
        else: self.status_field.color = None
        try: self.status_field.update()
        except: pass

    def get_data(self):
        return {
            "title": self.title_field.value or "",
            "task": self.task_field.value or "",
            "start_date": self.start_date_field.value or "",
            "end_date": self.end_date_field.value or "",
            "status": self.status_field.value or "Ongoing",
            "priority": self.priority_field.value or "Normal",
        }

    def save(self, e=None):
        if self.auto_save_timer:
            self.auto_save_timer.cancel()

        if self.has_date_error:
            if hasattr(self, 'page') and self.page:
                self.page.snack_bar = ft.SnackBar(ft.Text("Cannot save: Start date cannot be after end date"), bgcolor=ft.Colors.RED_400)
                self.page.snack_bar.open = True
                self.page.update()
            return
        self.on_save(self, self.get_data())
        self._update_original_data()
        self.attachments_changed = False
        self._show_save_indicator()
        if hasattr(self.page, 'app_instance'):
            self.page.app_instance.check_all_due_dates()

    def delete(self, e=None):
        self.on_delete(self)

# ---- EditableTabLabel e dialogs ----
class EditableTabLabel(ft.Row):
    def __init__(self, text, on_rename, scale):
        super().__init__(alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
        self.scale = scale
        self.text = text; self.on_rename = on_rename
        self.display_text = ft.Text(self.text, size=self.scale(14), weight=ft.FontWeight.BOLD)
        self.clickable_text = ft.GestureDetector(content=self.display_text, on_double_tap=self.start_editing)
        self.edit_field = ft.TextField(value=self.text, border="none", read_only=False, width=self.scale(120), on_submit=self.finish_editing, on_blur=self.finish_editing)
        self.edit_field.visible = False
        self.controls = [self.clickable_text, self.edit_field]

    def start_editing(self, e):
        self.clickable_text.visible = False; self.edit_field.visible = True; self.edit_field.value = self.text; self.edit_field.focus(); self.update()

    def finish_editing(self, e):
        new_name = self.edit_field.value; old_name = self.text
        if new_name and new_name != old_name:
            if self.on_rename: self.on_rename(old_name, new_name)
            self.text = new_name
        self.clickable_text.visible = True; self.edit_field.visible = False; self.display_text.value = new_name if new_name else old_name; self.update()

class DeleteConfirmationDialog(ft.AlertDialog):
    def __init__(self, on_confirm, on_cancel, scale):
        super().__init__()
        self.on_confirm = on_confirm; self.on_cancel = on_cancel
        self.scale = scale
        self.confirmation_text = ft.TextField(width=self.scale(300)); self.title = ft.Text()
        self.error_text = ft.Text("Text does not match. Try again.", color="red", visible=False)
        self.content = ft.Column([ft.Text("This action cannot be undone."), self.confirmation_text, self.error_text], tight=True)
        self.actions = [ft.TextButton("Cancel", on_click=self.cancel), ft.TextButton("Delete", on_click=self.confirm)]
        self.actions_alignment = ft.MainAxisAlignment.END

    def set_tab_name(self, tab_name):
        self.current_tab_name = tab_name
        self.title = ft.Text(f"Delete tab '{tab_name}'?")
        self.confirmation_text.label = f"Type '{tab_name}' to confirm"
        self.confirmation_text.value = ""; self.error_text.visible = False

    def confirm(self, e):
        if self.confirmation_text.value == self.current_tab_name:
            self.on_confirm(self.current_tab_name)
        else:
            self.error_text.visible = True; self.update()

    def cancel(self, e):
        self.on_cancel()

class DeleteTaskConfirmationDialog(ft.AlertDialog):
    def __init__(self, on_confirm, on_cancel, scale):
        super().__init__()
        self.on_confirm = on_confirm; self.on_cancel = on_cancel; self.random_code = ""
        self.scale = scale
        self.confirmation_text = ft.TextField(width=self.scale(300)); self.title = ft.Text("Delete task?")
        self.error_text = ft.Text("Code does not match. Try again.", color="red", visible=False)
        self.code_display_text = ft.Text(weight=ft.FontWeight.BOLD)
        self.content = ft.Column([ft.Text("This action cannot be undone."), ft.Text("To confirm, type the code below:"), self.code_display_text, self.confirmation_text, self.error_text], tight=True, spacing=10)
        self.actions = [ft.TextButton("Cancel", on_click=self.cancel), ft.TextButton("Delete", on_click=self.confirm)]
        self.actions_alignment = ft.MainAxisAlignment.END

    def generate_random_code(self, length=5):
        letters = string.ascii_uppercase
        self.random_code = ''.join(random.choice(letters) for _ in range(length))

    def open_dialog(self):
        self.generate_random_code()
        self.code_display_text.value = self.random_code
        self.confirmation_text.label = f"Type '{self.random_code}' to confirm"
        self.confirmation_text.value = ""; self.error_text.visible = False; self.open = True

    def confirm(self, e):
        if self.confirmation_text.value == self.random_code:
            self.open = False; self.on_confirm()
        else:
            self.error_text.visible = True; self.update()

    def cancel(self, e):
        self.open = False; self.on_cancel()

class AttachFileDialog(ft.AlertDialog):
    def __init__(self, on_confirm):
        super().__init__(); self.on_confirm = on_confirm
        self.title = ft.Text("Attach files to task"); self.tasks_dropdown = ft.Dropdown()
        self.content = ft.Column([ft.Text("Select a task to attach the files to:"), self.tasks_dropdown], tight=True)
        self.actions = [ft.TextButton("Cancel", on_click=self.cancel), ft.TextButton("Attach", on_click=self.confirm)]
        self.actions_alignment = ft.MainAxisAlignment.END

    def open_dialog(self, tasks):
        self.tasks_dropdown.options.clear()
        for task in tasks:
            self.tasks_dropdown.options.append(ft.dropdown.Option(key=task["id"], text=task["title"]))
        self.open = True
        if self.page: self.page.update()

    def cancel(self, e):
        self.open = False
        if self.page: self.page.update()

    def confirm(self, e):
        self.open = False
        if self.page:
            self.on_confirm(self.tasks_dropdown.value)
            self.page.update()

class SettingsDialog(ft.AlertDialog):
    def __init__(self, on_auto_save_toggle, initial_value, on_close, on_dpi_change, initial_dpi_scale):
        super().__init__()
        self.on_auto_save_toggle = on_auto_save_toggle
        self.on_close = on_close
        self.on_dpi_change = on_dpi_change
        self.title = ft.Text("Settings")
        self.auto_save_checkbox = ft.Checkbox(
            label="Auto save changes on tasks",
            value=initial_value,
            on_change=self.on_auto_save_toggle
        )

        dpi_options = {
            "75%": "0.75",
            "100%": "1.0",
            "125%": "1.25",
            "150%": "1.5",
        }
        initial_dpi_value = str(initial_dpi_scale)

        self.dpi_dropdown = ft.Dropdown(
            label="Display Scaling (requires restart)",
            options=[ft.dropdown.Option(key=v, text=k) for k, v in dpi_options.items()],
            value=initial_dpi_value,
            on_change=self._handle_dpi_change
        )

        self.content = ft.Column([self.auto_save_checkbox, self.dpi_dropdown], tight=True, spacing=15)
        self.actions = [ft.TextButton("Close", on_click=self.close_dialog)]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _handle_dpi_change(self, e):
        self.on_dpi_change(float(e.control.value))

    def close_dialog(self, e):
        self.open = False
        self.on_close()

# ---- AgendaTab ----
class AgendaTab(ft.Column):
    PRIORITY_ORDER = {"Critical": 0, "Normal": 1, "Not Urgent": 2}

    def __init__(self, tab_name, on_delete_tab_request, page, delete_dialog, get_auto_save_setting, scale):
        self.tab_name = tab_name
        self.on_delete_tab_request = on_delete_tab_request
        self.page = page
        self.delete_dialog = delete_dialog
        self.reorder_mode_active = False

        # ListView simples sem DragTarget para tasks
        self.get_auto_save_setting = get_auto_save_setting
        self.scale = scale # Store scale function
        self.ongoing_list = ft.ListView(expand=True, spacing=self.scale(10), padding=self.scale(10))
        self.complete_list = ft.ListView(expand=True, spacing=self.scale(10), padding=self.scale(10))

        self.task_to_delete = None
        self.delete_task_dialog = DeleteTaskConfirmationDialog(on_confirm=self.confirm_delete_task, on_cancel=self.cancel_delete_task, scale=self.scale)

        self.inner_tabs = ft.Tabs(tabs=[
            ft.Tab(text="Ongoing", content=ft.Container(self.ongoing_list, expand=True, padding=self.scale(10))), 
            ft.Tab(text="Complete", content=ft.Container(self.complete_list, expand=True, padding=self.scale(10)))
        ], expand=True)

        self.reorder_mode_btn = ft.IconButton(
            icon=ft.Icons.SWAP_VERT,
            tooltip="Enable reordering",
            on_click=self.toggle_reorder_mode
        )
        self.toggle_all_tasks_btn = ft.IconButton(
            icon=ft.Icons.UNFOLD_MORE,
            tooltip="Maximize All",
            on_click=self.toggle_all_tasks
        )
        self.add_task_btn = ft.ElevatedButton(text="Add Task", icon=ft.Icons.ADD, on_click=self.add_task)
        self.delete_tab_btn = ft.IconButton(icon=ft.Icons.DELETE, tooltip="Delete Tab", on_click=lambda e: self.on_delete_tab_request(self.tab_name))
        self.buttons_row = ft.Row([self.reorder_mode_btn, self.toggle_all_tasks_btn, ft.Container(expand=True), self.add_task_btn, self.delete_tab_btn], alignment=ft.MainAxisAlignment.END, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=self.scale(10))

        super().__init__(spacing=self.scale(12), expand=True, controls=[self.inner_tabs, self.buttons_row])

    def toggle_reorder_mode(self, e):
        self.reorder_mode_active = not self.reorder_mode_active
        
        if self.reorder_mode_active:
            self.reorder_mode_btn.icon = ft.Icons.LOCK
            self.reorder_mode_btn.tooltip = "Disable reordering (lock order)"
            self.reorder_mode_btn.icon_color = ft.Colors.AMBER
        else:
            self.reorder_mode_btn.icon = ft.Icons.SWAP_VERT
            self.reorder_mode_btn.tooltip = "Enable reordering"
            self.reorder_mode_btn.icon_color = None

        all_tasks = self.ongoing_list.controls + self.complete_list.controls
        for task in all_tasks:
            if isinstance(task, TaskRow):
                task.set_reorder_mode(self.reorder_mode_active)
                # Minimiza todas as tarefas ao entrar no modo de reordenação
                if self.reorder_mode_active:
                    task.set_minimized(True)
        if self.reorder_mode_active:
            self.update_arrow_states()
        try:
            self.update()
        except: pass

    def toggle_all_tasks(self, e):
        all_tasks = self.ongoing_list.controls + self.complete_list.controls
        if not all_tasks:
            return

        should_minimize = any(not task.is_minimized for task in all_tasks)

        for task in all_tasks:
            task.set_minimized(should_minimize)

        if should_minimize:
            self.toggle_all_tasks_btn.icon = ft.Icons.UNFOLD_MORE
            self.toggle_all_tasks_btn.tooltip = "Maximize All"
        else:
            self.toggle_all_tasks_btn.icon = ft.Icons.UNFOLD_LESS
            self.toggle_all_tasks_btn.tooltip = "Minimize All"
        try:
            self.toggle_all_tasks_btn.update()
        except:
            pass

    def load_tasks(self):
        tasks = db.list_tasks(self.tab_name)
        tasks.sort(key=lambda t: self.PRIORITY_ORDER.get(t.get("priority", "Normal"), 99))

        for t in tasks:
            row = TaskRow(self.on_save_task, self.on_delete_task, self.on_move_task_up, self.on_move_task_down, title=t["title"], task=t["task"], start_date=t["start_date"], end_date=t["end_date"], status=t["status"], priority=t["priority"], db_id=t["id"], get_auto_save_setting=self.get_auto_save_setting, scale=self.scale)
            if t["status"] == "Ongoing":
                self.ongoing_list.controls.append(row)
            else:
                self.complete_list.controls.append(row)
        self.update_arrow_states()
        try: self.update()
        except: pass

    def add_task(self, e=None):
        row = TaskRow(self.on_save_task, self.on_delete_task, self.on_move_task_up, self.on_move_task_down, get_auto_save_setting=self.get_auto_save_setting, scale=self.scale)
        row.set_reorder_mode(self.reorder_mode_active)
        self.add_row_to_list(row, row.status_field.value)
        self.update_arrow_states()
        if self.get_auto_save_setting and self.get_auto_save_setting():
            row.save()
        try: self.update()
        except: pass
        return row

    def add_row_to_list(self, row, status):
        if status == "Ongoing":
            self.ongoing_list.controls.insert(0, row)
        else:
            self.complete_list.controls.insert(0, row)

    def on_move_task_up(self, task_row):
        self._move_task(task_row, -1)

    def on_move_task_down(self, task_row):
        self._move_task(task_row, 1)

    def _move_task(self, task_row, direction: int):
        active_list = self.ongoing_list if task_row.status_field.value == "Ongoing" else self.complete_list
        
        try:
            current_index = active_list.controls.index(task_row)
        except ValueError:
            return

        new_index = current_index + direction
        if 0 <= new_index < len(active_list.controls):
            active_list.controls.pop(current_index)
            active_list.controls.insert(new_index, task_row)
            self.update_arrow_states()
            try:
                self.update()
            except:
                pass

    def update_arrow_states(self):
        for lst in (self.ongoing_list, self.complete_list):
            controls = lst.controls
            for i, task in enumerate(controls):
                if isinstance(task, TaskRow):
                    task.move_up_btn.disabled = (i == 0)
                    task.move_down_btn.disabled = (i == len(controls) - 1)
                    try:
                        task.update()
                    except:
                        pass

    def on_save_task(self, row, data):
        is_new_task = not row.db_id
        status_changed = is_new_task or (row.original_data.get("status") != data.get("status"))

        if row.db_id:
            db.update_task(row.db_id, data["title"], data["task"], data["start_date"], data["end_date"], data["status"], data["priority"], self.tab_name)
        else:
            row.db_id = db.add_task(self.tab_name, data["title"], data["task"], data["start_date"], data["end_date"], data["status"], data["priority"])
        if is_new_task and row.db_id:
            row.attach_btn.disabled = False
            row.display_id_text.value = f"#{row.db_id}"
            row.display_id_text.visible = True
            row._update_minimized_info()
            row._load_attachments()
            try: row.update()
            except: pass
        # Apenas move a tarefa se for nova ou se o status mudou
        if status_changed:
            self.move_task(row)

    def on_delete_task(self, row):
        self.task_to_delete = row
        if self.delete_task_dialog not in self.page.overlay:
            self.page.overlay.append(self.delete_task_dialog)
        self.delete_task_dialog.open_dialog()
        try: self.page.update()
        except: pass

    def confirm_delete_task(self):
        row = self.task_to_delete
        if row:
            if row.db_id:
                db.delete_task(row.db_id)
            for lst in (self.ongoing_list, self.complete_list):
                if row in lst.controls:
                    try: lst.controls.remove(row)
                    except: pass
        self.task_to_delete = None
        self.delete_task_dialog.open = False
        self.update_arrow_states()
        try: self.update()
        except: pass

    def cancel_delete_task(self):
        self.task_to_delete = None
        self.delete_task_dialog.open = False
        try: self.update()
        except: pass

    def move_task(self, row):
        # remove any existing occurrence
        for lst in (self.ongoing_list, self.complete_list):
            if row in lst.controls:
                try: lst.controls.remove(row)
                except: pass
        # reinsert according to current status
        self.add_row_to_list(row, row.status_field.value)
        self.update_arrow_states()
        try: self.update()
        except: pass

    def on_task_status_change(self, row):
        self.move_task(row)
        self.on_save_task(row, row.get_data())

# ---- AgendaApp ----
class AgendaApp(ft.Column):
    def __init__(self, page):
        super().__init__(spacing=12, expand=True)
        self.page = page
        
        self.dpi_scale = float(db.get_setting('dpi_scale', '1.0'))
        self.scale = lambda value: int(value * self.dpi_scale)

        self.tabs = ft.Tabs(selected_index=0, scrollable=True, expand=True)
        self.auto_save_enabled = db.get_setting('auto_save', 'False') == 'True'
        self.settings_dialog = SettingsDialog(
            on_auto_save_toggle=self.toggle_auto_save, 
            initial_value=self.auto_save_enabled, 
            on_close=self.close_settings_dialog,
            on_dpi_change=self.change_dpi,
            initial_dpi_scale=self.dpi_scale
        )
        self.delete_dialog = DeleteConfirmationDialog(on_confirm=self.delete_tab, on_cancel=self.close_delete_dialog, scale=self.scale)
        self.add_tab_btn = ft.ElevatedButton(text="New Tab", icon=ft.Icons.ADD, on_click=self.add_new_tab)
        
        self.settings_btn = ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="Settings", on_click=self.open_settings_dialog)
        self.pin_switch = ft.Switch(value=False, on_change=self.toggle_pin, tooltip="Pin window open")
        self.header = ft.Row([
            ft.Text("📒 TODO", style=ft.TextThemeStyle.HEADLINE_SMALL), 
            ft.Container(expand=True), 
            self.settings_btn, 
            self.pin_switch, self.add_tab_btn
        ])
        
        self.controls = [self.header, self.tabs]
        self.start_notification_checker()

    def toggle_auto_save(self, e):
        self.auto_save_enabled = e.control.value
        db.set_setting('auto_save', self.auto_save_enabled)

    def get_auto_save_setting(self):
        return self.auto_save_enabled

    def change_dpi(self, new_scale):
        db.set_setting('dpi_scale', new_scale)
        self.page.snack_bar = ft.SnackBar(ft.Text("Display scaling updated. Please restart the app."), bgcolor=ft.Colors.BLUE)
        self.page.snack_bar.open = True
        self.page.update()

    def open_settings_dialog(self, e):
        if self.settings_dialog not in self.page.overlay:
            self.page.overlay.append(self.settings_dialog)
        self.settings_dialog.open = True
        self.page.update()

    def close_settings_dialog(self, e=None):
        self.page.update()

    def start_notification_checker(self):
        self.notification_checker_thread = threading.Thread(target=self.check_due_dates_periodically, daemon=True)
        self.notification_checker_thread.start()

    def check_due_dates_periodically(self):
        while True:
            time.sleep(3600)  # Check every hour
            try:
                if self.page:
                    self.page.run_threadsafe(self.check_all_due_dates)
            except Exception as e:
                print(f"Error in periodic due date checker: {e}")

    def check_all_due_dates(self):
        if not self.page: return
        
        all_tasks = []
        for tab in self.tabs.tabs:
            agenda_tab = tab.content
            if isinstance(agenda_tab, AgendaTab):
                all_tasks.extend(agenda_tab.ongoing_list.controls)

        for task_row in all_tasks:
            if not isinstance(task_row, TaskRow) or task_row.status_field.value != "Ongoing":
                task_row.set_notification_status(None) # Reset color
                continue

            end_date_str = task_row.end_date_field.value
            if not (end_date_str and (end_date := task_row._parse_date(end_date_str))):
                task_row.set_notification_status(None) # Reset color
                continue

            days_diff = (end_date - datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).days
            status = "overdue" if days_diff < 0 else "upcoming" if 0 <= days_diff <= 3 else None
            
            task_row.set_notification_status(status, days_diff)

    def toggle_pin(self, e):
        self.page.pinned = self.pin_switch.value
        if self.page.pinned:
            self.page.window.width = 650; self.page.window.height = 900; self.page.app_container.opacity = 1; self.page.mini_icon.visible = False
            try: self.page.update()
            except: pass

    def open_delete_dialog_request(self, tab_name):
        if self.delete_dialog not in self.page.overlay:
            self.page.overlay.append(self.delete_dialog)
        self.delete_dialog.set_tab_name(tab_name)
        self.delete_dialog.open = True
        try: self.page.update()
        except: pass

    def close_delete_dialog(self, e=None):
        self.delete_dialog.open = False
        try: self.page.update()
        except: pass

    def load_tabs(self):
        tab_names = db.list_tabs()
        if not tab_names:
            db.add_tab("Tab 1"); tab_names = ["Tab 1"]
        self.tabs.tabs.clear()
        for name in tab_names:
            tab_content = AgendaTab(name, self.open_delete_dialog_request, self.page, self.delete_dialog, self.get_auto_save_setting, self.scale)
            editable_label = EditableTabLabel(name, self.rename_tab, self.scale)
            tab = ft.Tab(content=tab_content, tab_content=editable_label)
            self.tabs.tabs.append(tab)
        for t in self.tabs.tabs:
            try:
                t.content.load_tasks()
            except Exception:
                pass
        try: self.tabs.update()
        except: pass

    def _create_tab(self, tab_name):
        db.add_tab(tab_name)
        tab_content = AgendaTab(tab_name, self.open_delete_dialog_request, self.page, self.delete_dialog, self.get_auto_save_setting, self.scale)
        editable_label = EditableTabLabel(tab_name, self.rename_tab, self.scale)
        tab = ft.Tab(content=tab_content, tab_content=editable_label)
        self.tabs.tabs.append(tab)
        try:
            tab_content.load_tasks()
            self.tabs.update()
        except: pass

    def add_new_tab(self, e=None):
        existing_tab_count = len(self.tabs.tabs)
        new_tab_name = f"Tab {existing_tab_count + 1}"
        all_names = [t.tab_content.text for t in self.tabs.tabs]
        count = 1
        while new_tab_name in all_names:
            new_tab_name = f"Tab {existing_tab_count + 1 + count}"
            count += 1
        db.add_tab(new_tab_name)
        self._create_tab(new_tab_name)
        self.tabs.selected_index = len(self.tabs.tabs) - 1

    def rename_tab(self, old_name, new_name):
        for tab in self.tabs.tabs:
            if isinstance(tab.tab_content, EditableTabLabel) and tab.tab_content.text == old_name:
                tab.tab_content.text = new_name
                tab.tab_content.display_text.value = new_name
                db.update_tab_name(old_name, new_name)
                tab.content.tab_name = new_name
                try: self.tabs.update()
                except: pass
                return

    def delete_tab(self, tab_name):
        self.close_delete_dialog()
        if len(self.tabs.tabs) <= 1:
            self.page.snack_bar = ft.SnackBar(ft.Text("It is not possible to delete the last tab"))
            self.page.snack_bar.open = True
            try: self.page.update()
            except: pass
            return
        tab_to_remove = None
        for tab in self.tabs.tabs:
            if isinstance(tab.tab_content, EditableTabLabel) and tab.tab_content.text == tab_name:
                tab_to_remove = tab; break
        if tab_to_remove:
            db.delete_tab(tab_name)
            try: self.tabs.tabs.remove(tab_to_remove)
            except: pass
            if self.tabs.selected_index >= len(self.tabs.tabs):
                self.tabs.selected_index = len(self.tabs.tabs) - 1
            try: self.tabs.update()
            except: pass

# ---- main ----
def main(page: ft.Page):
    page.title = "Todo APP"
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.window.resizable = False
    page.window.always_on_top = True

    db.init_db()
    app = AgendaApp(page)
    page.app_instance = app

    # Apply scaling to window and top-level containers
    scale = app.scale
    page.window.width = scale(650)
    page.window.height = scale(900)

    page.app_container = ft.Container(content=app, expand=True, opacity=1, animate_opacity=ft.Animation(0), padding=scale(15))
    page.mini_icon = ft.Container(
        width=scale(100), height=scale(100), 
        alignment=ft.alignment.center, 
        content=ft.Icon(ft.Icons.EVENT_NOTE, size=scale(60), color=ft.Colors.BLUE), 
        visible=False)
    stack = ft.Stack(expand=True, controls=[page.app_container, page.mini_icon])
    page.add(stack)

    app.load_tabs()
    # Initial check on startup
    app.check_all_due_dates()

    page.pinned = False

    def position_window():
        try:
            screen_w, screen_h = pyautogui.size()
            page.window.left = screen_w - page.window.width - 50
            page.window.top = 10
            try: page.update()
            except: pass
        except Exception:
            pass

    def check_mouse():
        while True:
            try:
                if page.pinned:
                    time.sleep(0.1); continue
                mx, my = pyautogui.position()
                x0, y0 = page.window.left, page.window.top
                x1, y1 = x0 + page.window.width, y0 + page.window.height
                entered = x0 <= mx <= x1 and y0 <= my <= y1
                if getattr(page, "is_picker_open", False) or getattr(page, "is_file_picker_open", False):
                    entered = True
                if entered:
                    page.window.width = scale(650); page.window.height = scale(900); page.app_container.opacity = 1; page.mini_icon.visible = False
                else:
                    page.window.width = scale(100); page.window.height = scale(100); page.app_container.opacity = 0; page.mini_icon.visible = True
                position_window()
                try: page.update()
                except: pass
                time.sleep(0.05)
            except Exception:
                time.sleep(0.1)

    threading.Thread(target=check_mouse, daemon=True).start()
    position_window()
    try: page.update()
    except: pass

if __name__ == "__main__":
    ft.app(target=main)