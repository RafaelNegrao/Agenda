import flet as ft
import sqlite3
from datetime import datetime
import pyautogui
import threading
import time

import random
import string
BLUE_GOOGLE_DARK = "#2C2F48"
TITLE_FONT_SIZE = 16
FIELD_FONT_SIZE = 12
FIELD_SPACING = 12

# Simulação do módulo db para que o código funcione sem dependências externas
class db:
    @staticmethod
    def init_db():
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS tabs
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS tasks
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          tab_name TEXT, 
                          title TEXT,
                          task TEXT, 
                          start_date TEXT, 
                          end_date TEXT, 
                          status TEXT,
                          priority TEXT)''')
        conn.commit()
        conn.close()

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
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_tab(tab_name):
        conn = sqlite3.connect('agenda.db')
        c = conn.cursor()
        c.execute("DELETE FROM tabs WHERE name = ?", (tab_name,))
        c.execute("DELETE FROM tasks WHERE tab_name = ?", (tab_name,))
        conn.commit()
        conn.close()



class TaskRow(ft.Container):
    months = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }

    def __init__(self, on_save, on_delete, title=None, task=None, start_date=None, end_date=None, status=None, priority=None, db_id=None):
        self.on_save = on_save
        self.on_delete = on_delete
        self.db_id = db_id
        
        # Estado para controlar indicadores visuais
        self.has_changes = False
        self.is_saving = False
        self.has_date_error = False
        
        # Armazenar valores originais para detectar mudanças
        self.original_data = {
            "title": title or "",
            "task": task or "",
            "start_date": start_date or "",
            "end_date": end_date or "",
            "status": status or "Ongoing",
            "priority": priority or "Normal"
        }

        # Title
        self.title_field = ft.TextField(
            value=title or "",
            label="Title",
            expand=True,
            border=ft.InputBorder.UNDERLINE,
            text_style=ft.TextStyle(size=TITLE_FONT_SIZE, weight=ft.FontWeight.BOLD),
            content_padding=ft.padding.symmetric(vertical=15, horizontal=10),
            on_change=self._on_field_change
        )

        # Task
        self.task_field = ft.TextField(
            value=task or "",
            label="Task",
            multiline=True,
            min_lines=2,
            max_lines=6,
            expand=True,
            text_style=ft.TextStyle(size=FIELD_FONT_SIZE),
            content_padding=ft.padding.symmetric(vertical=20, horizontal=10),
            on_change=self._on_field_change
        )

        # Date pickers
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

        # Date fields
        self.start_date_field = ft.TextField(
            value=start_date or "",
            label="Start date",
            width=150,
            read_only=True,
            border=ft.InputBorder.UNDERLINE,
            content_padding=ft.padding.symmetric(vertical=15, horizontal=10),
            text_style=ft.TextStyle(size=FIELD_FONT_SIZE),
            suffix=ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                on_click=self._open_start_date_picker
            )
        )
        self.end_date_field = ft.TextField(
            value=end_date or "",
            label="End date",
            width=150,
            read_only=True,
            border=ft.InputBorder.UNDERLINE,
            content_padding=ft.padding.symmetric(vertical=15, horizontal=10),
            text_style=ft.TextStyle(size=FIELD_FONT_SIZE),
            suffix=ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                on_click=self._open_end_date_picker
            )
        )

        # Status dropdown
        self.status_field = ft.Dropdown(
            options=[ft.dropdown.Option("Ongoing"), ft.dropdown.Option("Complete")],
            value=status or "Ongoing",
            width=150,
            border=ft.InputBorder.UNDERLINE,
            border_radius=0,
            text_style=ft.TextStyle(size=FIELD_FONT_SIZE),
            content_padding=ft.padding.symmetric(vertical=15, horizontal=10),
            on_change=self._on_status_dropdown_change
        )

        # Priority dropdown
        self.priority_field = ft.Dropdown(
            options=[
                ft.dropdown.Option("Not Urgent"),
                ft.dropdown.Option("Normal"),
                ft.dropdown.Option("Critical")
            ],
            value=priority or "Normal",
            width=150,
            border=ft.InputBorder.UNDERLINE,
            border_radius=0,
            text_style=ft.TextStyle(size=FIELD_FONT_SIZE),
            content_padding=ft.padding.symmetric(vertical=15, horizontal=10),
            on_change=self._on_field_change
        )

        # Indicador de mudanças
        self.change_indicator = ft.Icon(
            ft.Icons.EDIT,
            color=ft.Colors.ORANGE,
            size=20,
            visible=False,
            tooltip="Unsaved changes"
        )
        
        # Indicador de salvamento
        self.save_indicator = ft.Icon(
            ft.Icons.CHECK_CIRCLE,
            color=ft.Colors.GREEN,
            size=20,
            visible=False,
            tooltip="Saved"
        )

        # Indicador de erro de data
        self.date_error_indicator = ft.Icon(
            ft.Icons.ERROR,
            color=ft.Colors.RED,
            size=20,
            visible=False,
            tooltip="Start date cannot be after end date"
        )

        # Texto de erro de data
        self.date_error_text = ft.Text(
            "Start date cannot be after end date",
            color=ft.Colors.RED,
            size=12,
            visible=False
        )

        # Buttons
        self.save_btn = ft.IconButton(
            icon=ft.Icons.SAVE, 
            tooltip="Save", 
            on_click=self.save,
            disabled=False
        )
        self.delete_btn = ft.IconButton(icon=ft.Icons.DELETE, tooltip="Delete", on_click=self.delete)

        # Indicadores row
        indicators_row = ft.Row(
            [self.change_indicator, self.save_indicator, self.date_error_indicator],
            spacing=5,
            alignment=ft.MainAxisAlignment.START
        )

        # Rows
        status_row = ft.Row(
            [self.start_date_field, self.end_date_field],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=FIELD_SPACING,
        )

        priority_status_row = ft.Row(
            [
                self.priority_field, 
                self.status_field, 
                ft.Container(expand=True), 
                indicators_row,
                self.save_btn, 
                self.delete_btn
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=FIELD_SPACING,
        )

        inner = ft.Column(
            [
                self.title_field, 
                self.task_field, 
                status_row, 
                self.date_error_text,
                priority_status_row
            ],
            spacing=FIELD_SPACING,
        )

        super().__init__(content=inner, padding=20, bgcolor=BLUE_GOOGLE_DARK, border_radius=20, margin=ft.margin.only(bottom=10))

        self._on_status_change()
        self._validate_dates()

    def _parse_date(self, date_str):
        """Converte string de data no formato DD/MMM/YYYY para datetime"""
        if not date_str:
            return None
        try:
            # Formato: "01/Jan/2024"
            parts = date_str.split('/')
            if len(parts) != 3:
                return None
            
            day = int(parts[0])
            month_name = parts[1]
            year = int(parts[2])
            
            # Converter nome do mês para número
            month_names = {v: k for k, v in self.months.items()}
            month = month_names.get(month_name)
            if not month:
                return None
            
            return datetime(year, month, day)
        except (ValueError, TypeError):
            return None

    def _validate_dates(self):
        """Valida se a data de início não é posterior à data de fim"""
        start_date = self._parse_date(self.start_date_field.value)
        end_date = self._parse_date(self.end_date_field.value)
        
        # Se alguma data não existe, não há erro
        if not start_date or not end_date:
            self._clear_date_error()
            return True
        
        # Se data de início é posterior à data de fim, há erro
        if start_date > end_date:
            self._show_date_error()
            return False
        else:
            self._clear_date_error()
            return True

    def _show_date_error(self):
        """Mostra indicadores de erro de data"""
        self.has_date_error = True
        self.date_error_indicator.visible = True
        self.date_error_text.visible = True
        self.save_btn.disabled = True
        
        # Deixar os campos de data com borda vermelha
        self.start_date_field.border_color = ft.Colors.RED
        self.end_date_field.border_color = ft.Colors.RED
        
        if hasattr(self, 'page') and self.page:
            self.update()

    def _clear_date_error(self):
        """Remove indicadores de erro de data"""
        self.has_date_error = False
        self.date_error_indicator.visible = False
        self.date_error_text.visible = False
        self.save_btn.disabled = False
        
        # Restaurar cor normal das bordas
        self.start_date_field.border_color = None
        self.end_date_field.border_color = None
        
        if hasattr(self, 'page') and self.page:
            self.update()

    def _on_field_change(self, e=None):
        """Detecta mudanças nos campos e atualiza indicadores"""
        # Primeiro valida as datas
        dates_valid = self._validate_dates()
        
        # Depois verifica se há mudanças (só se as datas estão válidas)
        if dates_valid and self._has_data_changed():
            self._show_change_indicator()
        else:
            self._hide_change_indicator()

    def _on_status_dropdown_change(self, e=None):
        """Trata mudanças no dropdown de status"""
        self._on_status_change()
        self._on_field_change()
        
        # Auto-save apenas se não há erro de datas
        if not self.has_date_error:
            self.on_save(self, self.get_data())

    def _has_data_changed(self):
        """Verifica se os dados atuais diferem dos originais"""
        current_data = self.get_data()
        for key, value in current_data.items():
            if str(value) != str(self.original_data.get(key, "")):
                return True
        return False

    def _show_change_indicator(self):
        """Mostra o indicador de mudanças"""
        self.has_changes = True
        self.change_indicator.visible = True
        self.save_indicator.visible = False
        if hasattr(self, 'page') and self.page:
            self.update()

    def _hide_change_indicator(self):
        """Esconde o indicador de mudanças"""
        self.has_changes = False
        self.change_indicator.visible = False
        if hasattr(self, 'page') and self.page:
            self.update()

    def _show_save_indicator(self):
        """Mostra o indicador de salvamento"""
        self.save_indicator.visible = True
        self.change_indicator.visible = False
        if hasattr(self, 'page') and self.page:
            self.update()
        
        # Auto-hide após 2 segundos
        def hide_after_delay():
            import time
            time.sleep(2)
            if hasattr(self, 'page') and self.page:
                self.save_indicator.visible = False
                self.update()
        
        # Usar threading para não bloquear a UI
        import threading
        threading.Thread(target=hide_after_delay, daemon=True).start()

    def _update_original_data(self):
        """Atualiza os dados originais após salvamento"""
        self.original_data = self.get_data().copy()

    def did_mount(self):
        self.page.overlay.append(self.start_date_picker)
        self.page.overlay.append(self.end_date_picker)
        self.page.update()

    def will_unmount(self):
        self.page.overlay.remove(self.start_date_picker)
        self.page.overlay.remove(self.end_date_picker)
        self.page.update()

    def _format_date(self, date_obj: datetime):
        if not date_obj:
            return ""
        day = date_obj.day
        month = self.months.get(date_obj.month, "Inv")
        year = date_obj.year
        return f"{day:02d}/{month}/{year}"

    def _open_start_date_picker(self, e):
        self.page.is_picker_open = True
        self.page.open(self.start_date_picker)

    def _open_end_date_picker(self, e):
        self.page.is_picker_open = True
        self.page.open(self.end_date_picker)

    def _on_picker_dismiss(self, e):
        self.page.is_picker_open = False

    def _on_start_date_change(self, e):
        self.page.is_picker_open = False
        selected_date = e.control.value
        self.start_date_field.value = self._format_date(selected_date)
        self.start_date_picker.open = False
        self.start_date_field.update()
        self.page.update()
        # Detectar mudança na data e validar
        self._on_field_change()

    def _on_end_date_change(self, e):
        self.page.is_picker_open = False
        selected_date = e.control.value
        self.end_date_field.value = self._format_date(selected_date)
        self.end_date_picker.open = False
        self.end_date_field.update()
        self.page.update()
        # Detectar mudança na data e validar
        self._on_field_change()

    def _on_status_change(self, e=None):
        v = (self.status_field.value or "").lower()
        if v == "ongoing":
            self.status_field.color = "#FFA726"  # Orange
        elif v == "complete":
            self.status_field.color = "#66BB6A"  # Green
        else:
            self.status_field.color = None
        if hasattr(self.status_field, 'page') and self.status_field.page:
            self.status_field.update()

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
        """Salva as mudanças e atualiza indicadores"""
        # Não salvar se há erro de datas
        if self.has_date_error:
            if hasattr(self, 'page') and self.page:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text("Cannot save: Start date cannot be after end date"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
            return
        
        self.on_save(self, self.get_data())
        self._update_original_data()
        self._show_save_indicator()

    def delete(self, e=None):
        self.on_delete(self)


class EditableTabLabel(ft.Row):
    def __init__(self, text, on_rename):
        super().__init__(
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0
        )
        self.text = text
        self.on_rename = on_rename
        
        self.display_text = ft.Text(
            self.text,
            size=14,
            weight=ft.FontWeight.BOLD,
        )
        
        self.clickable_text = ft.GestureDetector(
            content=self.display_text,
            on_double_tap=self.start_editing
        )
        
        self.edit_field = ft.TextField(
            value=self.text,
            border="none",
            read_only=False,
            width=120,
            on_submit=self.finish_editing,
            on_blur=self.finish_editing
        )
        self.edit_field.visible = False
        
        self.controls = [self.clickable_text, self.edit_field]
        
    def start_editing(self, e):
        self.clickable_text.visible = False
        self.edit_field.visible = True
        self.edit_field.value = self.text
        self.edit_field.focus()
        self.update()

    def finish_editing(self, e):
        new_name = self.edit_field.value
        old_name = self.text
        
        if new_name and new_name != old_name:
            if self.on_rename:
                self.on_rename(old_name, new_name)
            self.text = new_name
        
        self.clickable_text.visible = True
        self.edit_field.visible = False
        self.display_text.value = new_name if new_name else old_name
        self.update()


class DeleteConfirmationDialog(ft.AlertDialog):
    def __init__(self, on_confirm, on_cancel):
        super().__init__()
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        
        self.confirmation_text = ft.TextField(width=300)
        self.title = ft.Text()
        
        self.error_text = ft.Text(
            "Text does not match. Try again.",
            color="red",
            visible=False
        )
        
        self.content = ft.Column(
            [
                ft.Text("This action cannot be undone."),
                self.confirmation_text,
                self.error_text
            ],
            tight=True
        )
        
        self.actions = [
            ft.TextButton("Cancel", on_click=self.cancel),
            ft.TextButton("Delete", on_click=self.confirm)
        ]
        
        self.actions_alignment = ft.MainAxisAlignment.END

    def set_tab_name(self, tab_name):
        self.current_tab_name = tab_name
        self.title = ft.Text(f"Delete tab '{tab_name}'?")
        self.confirmation_text.label = f"Type '{tab_name}' to confirm"
        self.confirmation_text.value = ""
        self.error_text.visible = False

    def check_confirmation(self, e):
        if self.confirmation_text.value == self.current_tab_name:
            self.on_confirm(self.current_tab_name)
        else:
            self.error_text.visible = True
            self.update()
    
    def confirm(self, e):
        if self.confirmation_text.value == self.current_tab_name:
            self.on_confirm(self.current_tab_name)
        else:
            self.error_text.visible = True
            self.update()
    
    def cancel(self, e):
        self.on_cancel()


class DeleteTaskConfirmationDialog(ft.AlertDialog):
    def __init__(self, on_confirm, on_cancel):
        super().__init__()
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.random_code = ""
        
        self.confirmation_text = ft.TextField(width=300)
        self.title = ft.Text("Delete task?")
        
        self.error_text = ft.Text(
            "Code does not match. Try again.",
            color="red",
            visible=False
        )
        
        self.code_display_text = ft.Text(weight=ft.FontWeight.BOLD)

        self.content = ft.Column(
            [
                ft.Text("This action cannot be undone."),
                ft.Text("To confirm, type the code below:"),
                self.code_display_text,
                self.confirmation_text,
                self.error_text
            ],
            tight=True,
            spacing=10
        )
        
        self.actions = [
            ft.TextButton("Cancel", on_click=self.cancel),
            ft.TextButton("Delete", on_click=self.confirm)
        ]
        
        self.actions_alignment = ft.MainAxisAlignment.END

    def generate_random_code(self, length=5):
        letters = string.ascii_uppercase
        self.random_code = ''.join(random.choice(letters) for _ in range(length))

    def open_dialog(self):
        self.generate_random_code()
        self.code_display_text.value = self.random_code
        self.confirmation_text.label = f"Type '{self.random_code}' to confirm"
        self.confirmation_text.value = ""
        self.error_text.visible = False
        self.open = True
    
    def confirm(self, e):
        if self.confirmation_text.value == self.random_code:
            self.open = False
            self.on_confirm()
        else:
            self.error_text.visible = True
            self.update()
    
    def cancel(self, e):
        self.open = False
        self.on_cancel()


class AgendaTab(ft.Column):
    PRIORITY_ORDER = {"Critical": 0, "Normal": 1, "Not Urgent": 2}

    def __init__(self, tab_name, on_delete_tab_request, page, delete_dialog):
        super().__init__(spacing=12, expand=True)
        self.tab_name = tab_name
        self.on_delete_tab_request = on_delete_tab_request
        self.page = page
        self.delete_dialog = delete_dialog
        self.ongoing_list = ft.ListView(expand=True, spacing=10, padding=10)
        self.complete_list = ft.ListView(expand=True, spacing=10, padding=10)

        self.task_to_delete = None
        self.delete_task_dialog = DeleteTaskConfirmationDialog(
            on_confirm=self.confirm_delete_task,
            on_cancel=self.cancel_delete_task
        )

        self.inner_tabs = ft.Tabs(
            tabs=[
                ft.Tab(text="Ongoing", content=ft.Container(self.ongoing_list, expand=True, padding=10)),
                ft.Tab(text="Complete", content=ft.Container(self.complete_list, expand=True, padding=10)),
            ],
            expand=True,
        )

        self.add_task_btn = ft.ElevatedButton(text="Add Task", icon=ft.Icons.ADD, on_click=self.add_task)
        self.delete_tab_btn = ft.IconButton(
            icon=ft.Icons.DELETE,
            tooltip="Delete Tab",
            on_click=lambda e: self.on_delete_tab_request(self.tab_name)
        )

        self.buttons_row = ft.Row(
            [ft.Container(expand=True), self.add_task_btn, self.delete_tab_btn],
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )

        self.controls = [self.inner_tabs, self.buttons_row]
        self.load_tasks()

    def load_tasks(self):
        tasks = db.list_tasks(self.tab_name)
        for t in tasks:
            row = TaskRow(
                self.on_save_task,
                self.on_delete_task,
                title=t["title"],
                task=t["task"],
                start_date=t["start_date"],
                end_date=t["end_date"],
                status=t["status"],
                priority=t["priority"],
                db_id=t["id"]
            )
            if t["status"] == "Ongoing":
                self._insert_sorted(self.ongoing_list, row)
            else:
                self._insert_sorted(self.complete_list, row)

    def add_task(self, e=None):
        row = TaskRow(self.on_save_task, self.on_delete_task)
        self.add_row_to_list(row, row.status_field.value)
        return row

    def add_row_to_list(self, row, status):
        if status == "Ongoing":
            self._insert_sorted(self.ongoing_list, row)
            self.ongoing_list.update()
        else:
            self._insert_sorted(self.complete_list, row)
            self.complete_list.update()

    def _insert_sorted(self, list_view, row):
        """Insere a task na posição correta de acordo com a prioridade."""
        order = self.PRIORITY_ORDER.get(row.priority_field.value, 99)
        inserted = False
        for i, ctrl in enumerate(list_view.controls):
            existing_order = self.PRIORITY_ORDER.get(ctrl.priority_field.value, 99)
            if order < existing_order:
                list_view.controls.insert(i, row)
                inserted = True
                break
        if not inserted:
            list_view.controls.append(row)

    def on_save_task(self, row, data):
        if row.db_id:
            db.update_task(
                row.db_id,
                data["title"],
                data["task"],
                data["start_date"],
                data["end_date"],
                data["status"],
                data["priority"],
                self.tab_name
            )
        else:
            row.db_id = db.add_task(
                self.tab_name,
                data["title"],
                data["task"],
                data["start_date"],
                data["end_date"],
                data["status"],
                data["priority"]
            )
        self.move_task(row)

    def on_delete_task(self, row):
        self.task_to_delete = row
        if self.delete_task_dialog not in self.page.overlay:
            self.page.overlay.append(self.delete_task_dialog)
        self.delete_task_dialog.open_dialog()
        self.page.update()

    def confirm_delete_task(self):
        row = self.task_to_delete
        if row:
            if row.db_id:
                db.delete_task(row.db_id)
            for lst in [self.ongoing_list, self.complete_list]:
                if row in lst.controls:
                    lst.controls.remove(row)
                    lst.update()
                    break
        self.task_to_delete = None
        self.delete_task_dialog.open = False
        self.page.update()

    def cancel_delete_task(self):
        self.task_to_delete = None
        self.delete_task_dialog.open = False
        self.page.update()

    def move_task(self, row):
        for lst in [self.ongoing_list, self.complete_list]:
            if row in lst.controls:
                lst.controls.remove(row)
                lst.update()
        self.add_row_to_list(row, row.status_field.value)
    
    def on_task_status_change(self, row):
        for lst in [self.ongoing_list, self.complete_list]:
            if row in lst.controls:
                lst.controls.remove(row)
                lst.update()
        self.add_row_to_list(row, row.status_field.value)
        self.on_save_task(row, row.get_data())


class AgendaApp(ft.Column):
    def __init__(self, page):
        super().__init__(spacing=12, expand=True)
        self.page = page
        self.tabs = ft.Tabs(selected_index=0, scrollable=True, expand=True)
        
        self.delete_dialog = DeleteConfirmationDialog(
            on_confirm=self.delete_tab, 
            on_cancel=self.close_delete_dialog
        )
        self.page.dialog = self.delete_dialog

        self.add_tab_btn = ft.ElevatedButton(
            text="New Tab", icon=ft.Icons.ADD, on_click=self.add_new_tab
        )
        
        self.header = ft.Row(
            [
                ft.Text("📒 Agenda", style=ft.TextThemeStyle.HEADLINE_SMALL),
                ft.Container(expand=True),
                self.add_tab_btn,
            ]
        )
        self.controls = [self.header, self.tabs]
        self.load_tabs()

    def open_delete_dialog_request(self, tab_name):
        if self.delete_dialog not in self.page.controls:
            self.page.add(self.delete_dialog)
        self.delete_dialog.set_tab_name(tab_name)
        self.delete_dialog.open = True
        self.page.update()

    def close_delete_dialog(self, e=None):
        self.delete_dialog.open = False
        self.page.update()

    def load_tabs(self):
        tab_names = db.list_tabs()
        if not tab_names:
            db.add_tab("Tab 1")
            self._create_tab("Tab 1")
        else:
            for name in tab_names:
                self._create_tab(name)

    def _create_tab(self, tab_name):
        tab_content = AgendaTab(tab_name, self.open_delete_dialog_request, self.page, self.delete_dialog)
        editable_label = EditableTabLabel(tab_name, self.rename_tab)
        tab = ft.Tab(
            content=tab_content,
            tab_content=editable_label
        )
        self.tabs.tabs.append(tab)

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
        self.tabs.update()

    def rename_tab(self, old_name, new_name):
        for tab in self.tabs.tabs:
            if isinstance(tab.tab_content, EditableTabLabel) and tab.tab_content.text == old_name:
                tab.tab_content.text = new_name
                tab.tab_content.display_text.value = new_name
                db.update_tab_name(old_name, new_name)
                # Update the tab name in the AgendaTab object as well
                tab.content.tab_name = new_name
                self.tabs.update()
                return
                
    def delete_tab(self, tab_name):
        self.close_delete_dialog()
        if len(self.tabs.tabs) <= 1:
            self.page.snack_bar = ft.SnackBar(ft.Text("It is not possible to delete the last tab"))
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        tab_to_remove = None
        for tab in self.tabs.tabs:
            if isinstance(tab.tab_content, EditableTabLabel) and tab.tab_content.text == tab_name:
                tab_to_remove = tab
                break
        
        if tab_to_remove:
            db.delete_tab(tab_name)
            self.tabs.tabs.remove(tab_to_remove)
            
            if self.tabs.selected_index >= len(self.tabs.tabs):
                self.tabs.selected_index = len(self.tabs.tabs) - 1
            
            self.tabs.update()
            self.page.update()


def main(page: ft.Page):
    page.title = "Agenda Dinâmica"
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.window.resizable = False
    page.window.always_on_top = True

    # tamanho inicial
    page.window.width = 650
    page.window.height = 900

    db.init_db()
    app = AgendaApp(page)

    page.app_container = ft.Container(
        content=app,
        expand=True,
        opacity=1,
        animate_opacity=ft.Animation(0),
        padding=15
    )

    page.mini_icon = ft.Container(
        width=100,
        height=100,
        alignment=ft.alignment.center,
        content=ft.Icon(ft.Icons.EVENT_NOTE, size=60, color=ft.Colors.BLUE),
        visible=False
    )

    stack = ft.Stack(expand=True, controls=[page.app_container, page.mini_icon])
    page.add(stack)
    page.update()

    def position_window():
        screen_w, screen_h = pyautogui.size()
        page.window.left = screen_w - page.window.width - 50
        page.window.top = 10
        page.update()

    def check_mouse():
        while True:
            try:
                mx, my = pyautogui.position()
                x0, y0 = page.window.left, page.window.top
                x1, y1 = x0 + page.window.width, y0 + page.window.height

                entered = x0 <= mx <= x1 and y0 <= my <= y1

                if getattr(page, "is_picker_open", False):
                    entered = True

                if entered:
                    page.window.width = 650
                    page.window.height = 900
                    page.app_container.opacity = 1
                    page.mini_icon.visible = False
                else:
                    page.window.width = 100
                    page.window.height = 100
                    page.app_container.opacity = 0
                    page.mini_icon.visible = True

                position_window()
                page.update()
                time.sleep(0.05)  # verifica a cada 50ms
            except Exception as e:
                print(e)

    threading.Thread(target=check_mouse, daemon=True).start()
    position_window()

if __name__ == "__main__":
    ft.app(target=main)