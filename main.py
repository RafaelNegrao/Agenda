import flet as ft
import sqlite3
from datetime import datetime
import uuid
import math
import threading
import time
import os
import shutil
import random
import sys
import string
import pyautogui
import ctypes

APP_NAME = "Todo APP"
VERSION = "1.1.0"
# On Windows, this will be C:\Users\<user>\AppData\Roaming\Todo APP
APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
DB_PATH = os.path.join(APP_DATA_DIR, 'agenda.db')
ATTACHMENTS_DIR = os.path.join(APP_DATA_DIR, 'attachments')

DRACULA_THEME = ft.Theme(
    color_scheme=ft.ColorScheme(
        background="#312447",
        on_background="#f8f8f2",
        surface="#282a36",
        on_surface="#f8f8f2",
        surface_variant="#483f61",  # Cor de fundo das tarefas (mais clara)
        on_surface_variant="#f8f8f2",
        primary="#bd93f9",  # Roxo
        on_primary="#000000",
        secondary="#ff79c9",  # Rosa
        on_secondary="#000000",
        error="#ff5555",  # Vermelho
        on_error="#000000",
        outline="#6272a4",
    ),
    page_transitions=ft.PageTransitionsTheme(
        android=ft.PageTransitionTheme.NONE,
        ios=ft.PageTransitionTheme.NONE,
        linux=ft.PageTransitionTheme.NONE,
        macos=ft.PageTransitionTheme.NONE,
        windows=ft.PageTransitionTheme.NONE,
    ), # Remove a animação de transição de página padrão
)

def get_auto_dpi_scale(base_dpi=96):
    """
    Calculates the UI scale factor based on the screen's DPI.
    Uses ctypes on Windows to avoid tkinter dependency issues in executables.
    """
    try:
        if sys.platform == "win32":
            # Set process DPI awareness to System Aware (1)
            # This is crucial for getting the correct DPI value in scaled displays.
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                # Fallback for older Windows versions
                ctypes.windll.user32.SetProcessDPIAware()
            
            # Get DPI
            LOGPIXELSX = 88  # Horizontal DPI
            hDC = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hDC, LOGPIXELSX)
            ctypes.windll.user32.ReleaseDC(0, hDC)
            return dpi / base_dpi
        else: # Fallback for other OS (macOS, Linux)
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            dpi = root.winfo_fpixels('1i')
            root.destroy()
            return dpi / base_dpi
    except Exception as e:
        print(f"Could not determine screen DPI, falling back to 1.0. Error: {e}")
        return 1.0

# ---- simple DB shim (igual ao seu) ----
class db:
    @staticmethod
    def init_db():
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
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
        c.execute("""CREATE TABLE IF NOT EXISTS checklist_items
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          task_id INTEGER,
                          text TEXT,
                          is_checked INTEGER,
                          FOREIGN KEY(task_id) REFERENCES tasks(id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings
                         (key TEXT PRIMARY KEY, value TEXT)""")
        conn.commit()
        conn.close()
        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

    @staticmethod
    def add_tab(name):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO tabs (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()

    @staticmethod
    def list_tabs():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name FROM tabs")
        tabs = [row[0] for row in c.fetchall()]
        conn.close()
        return tabs

    @staticmethod
    def update_tab_name(old_name, new_name):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE tabs SET name = ? WHERE name = ?", (new_name, old_name))
        c.execute("UPDATE tasks SET tab_name = ? WHERE tab_name = ?", (new_name, old_name))
        conn.commit()
        conn.close()

    @staticmethod
    def add_task(tab_name, title, task, start_date, end_date, status, priority):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO tasks (tab_name, title, task, start_date, end_date, status, priority) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (tab_name, title, task, start_date, end_date, status, priority))
        task_id = c.lastrowid
        conn.commit()
        conn.close()
        return task_id

    @staticmethod
    def list_tasks(tab_name):
        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE tasks SET title = ?, task = ?, start_date = ?, end_date = ?, status = ?, priority = ?, tab_name = ? WHERE id = ?",
                  (title, task, start_date, end_date, status, priority, tab_name, task_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_task(task_id):
        task_attachment_dir = os.path.join(ATTACHMENTS_DIR, str(task_id))
        if os.path.exists(task_attachment_dir):
            shutil.rmtree(task_attachment_dir)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM attachments WHERE task_id = ?", (task_id,))
        c.execute("DELETE FROM checklist_items WHERE task_id = ?", (task_id,))
        c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_tab(tab_name):
        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO attachments (task_id, file_path) VALUES (?, ?)", (task_id, file_path))
        conn.commit()
        conn.close()

    @staticmethod
    def list_attachments(task_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, file_path FROM attachments WHERE task_id = ?", (task_id,))
        attachments = [{"id": row[0], "file_path": row[1]} for row in c.fetchall()]
        conn.close()
        return attachments

    @staticmethod
    def get_attachment(attachment_id):
        conn = sqlite3.connect(DB_PATH)
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
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def list_checklist_items(task_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, text, is_checked FROM checklist_items WHERE task_id = ?", (task_id,))
        items = [{"id": row[0], "text": row[1], "is_checked": bool(row[2])} for row in c.fetchall()]
        conn.close()
        return items

    @staticmethod
    def add_checklist_item(task_id, text, is_checked):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO checklist_items (task_id, text, is_checked) VALUES (?, ?, ?)", (task_id, text, int(is_checked)))
        item_id = c.lastrowid
        conn.commit()
        conn.close()
        return item_id

    @staticmethod
    def update_checklist_item(item_id, text, is_checked):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE checklist_items SET text = ?, is_checked = ? WHERE id = ?", (text, int(is_checked), item_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete_checklist_item(item_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM checklist_items WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_setting(key, default=None):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = c.fetchone()
        conn.close()
        if result:
            return result[0]
        return default

    @staticmethod
    def set_setting(key, value):
        conn = sqlite3.connect(DB_PATH)
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

    def __init__(self, on_save, on_delete, on_duplicate, on_move_up, on_move_down, title=None, task=None, start_date=None, end_date=None, status=None, priority=None, db_id=None, get_auto_save_setting=None, scale=None, base_font_size=12):
        self.base_font_size = base_font_size
        self.on_save = on_save
        self.on_delete = on_delete
        self.on_duplicate = on_duplicate
        self.db_id = db_id
        self.is_minimized = False

        self.has_changes = False
        self.is_saving = False
        self.on_move_up = on_move_up
        self.on_move_down = on_move_down
        self.has_date_error = False
        self.attachments_changed = False
        self.checklist_changed = False
        self.notification_status = None
        self.get_auto_save_setting = get_auto_save_setting
        self.auto_save_timer = None
        self.scale_func = scale if scale else lambda x: x # Fallback for safety

        self.original_data = {
            "title": title or "",
            "task": task or "",
            "start_date": start_date or "",
            "end_date": end_date or "",
            "status": status or "Ongoing",
            "priority": priority or "Normal"
        }

        self.original_bgcolor = None # Será definido com base no tema

        self.display_id_text = ft.Text(
            f"#{db_id}" if db_id else "",
            size=self.scale_func(30),
            color=ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.BOLD,
            visible=db_id is not None
        )

        self.title_field = ft.TextField(
            value=title or "",
            label="Title",
            expand=True,
            border=ft.InputBorder.UNDERLINE,
            text_style=ft.TextStyle(size=self.scale_func(16), weight=ft.FontWeight.BOLD),
            content_padding=ft.padding.symmetric(vertical=self.scale_func(15), horizontal=self.scale_func(10)),
            on_change=self._on_field_change,
            capitalization=ft.TextCapitalization.CHARACTERS
        )

        self.task_field = ft.TextField(
            value=task or "",
            label="Task",
            multiline=True,
            min_lines=2,
            max_lines=6,
            expand=True,
            text_style=ft.TextStyle(size=self.scale_func(self.base_font_size)),
            content_padding=ft.padding.symmetric(vertical=self.scale_func(25), horizontal=self.scale_func(10)),
            on_change=self._on_field_change
        )

        self.checklist_col = ft.Column(spacing=self.scale_func(5))
        self.add_checklist_item_btn = ft.IconButton(icon=ft.Icons.ADD, on_click=self._add_checklist_item_ui, tooltip="Add checklist item")

        self.attachments_list = ft.Column(spacing=self.scale_func(5))
        self.progress_bar = ft.ProgressBar(visible=False, height=self.scale_func(10))

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
            padding=self.scale_func(20),
            visible=False,
            margin=ft.margin.symmetric(vertical=self.scale_func(10)),
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

        self.start_date_icon = ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self._open_start_date_picker,
            icon_size=self.scale_func(20),
            opacity=0,
            animate_opacity=ft.Animation(duration=200)
        )
        self.start_date_field = ft.TextField(
            value=start_date or "",
            label="Start date",
            read_only=True,
            border=ft.InputBorder.UNDERLINE,
            content_padding=ft.padding.only(
                left=self.scale_func(3), 
                top=self.scale_func(10), 
                bottom=self.scale_func(10), 
                right=self.scale_func(35)
            ),
            text_style=ft.TextStyle(size=self.scale_func(self.base_font_size)),
        )
        self.start_date_container = ft.Container(
            content=ft.Stack(
                [
                    self.start_date_field,
                    ft.Container(content=self.start_date_icon, alignment=ft.alignment.center_right)
                ]
            ),
            on_hover=lambda e: self._on_date_field_hover(e, self.start_date_icon),
            expand=2
        )

        self.end_date_icon = ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=self._open_end_date_picker,
            icon_size=self.scale_func(20),
            opacity=0,
            animate_opacity=ft.Animation(duration=200)
        )
        self.end_date_field = ft.TextField(
            value=end_date or "",
            label="End date",
            read_only=True,
            border=ft.InputBorder.UNDERLINE,
            content_padding=ft.padding.only(
                left=self.scale_func(3), 
                top=self.scale_func(10), 
                bottom=self.scale_func(10), 
                right=self.scale_func(35)
            ),
            text_style=ft.TextStyle(size=self.scale_func(self.base_font_size)),
        )
        self.end_date_container = ft.Container(
            content=ft.Stack(
                [
                    self.end_date_field,
                    ft.Container(content=self.end_date_icon, alignment=ft.alignment.center_right)
                ]
            ),
            on_hover=lambda e: self._on_date_field_hover(e, self.end_date_icon),
            expand=2
        )

        self.status_field = ft.Dropdown(
            label="Status",
            options=[ft.dropdown.Option("Ongoing"), ft.dropdown.Option("Complete")],
            value=status or "Ongoing",
            expand=2,
            border=ft.InputBorder.UNDERLINE,
            border_radius=0,
            text_style=ft.TextStyle(size=self.scale_func(self.base_font_size)),
            content_padding=ft.padding.symmetric(vertical=self.scale_func(10), horizontal=self.scale_func(3)),
            on_change=self._on_status_dropdown_change
        )

        self.priority_field = ft.Dropdown(
            label="Priority",
            options=[
                ft.dropdown.Option("Not Urgent"),
                ft.dropdown.Option("Normal"),
                ft.dropdown.Option("Critical")
            ],
            value=priority or "Normal",
            expand=2,
            border=ft.InputBorder.UNDERLINE,
            border_radius=0,
            text_style=ft.TextStyle(size=self.scale_func(self.base_font_size)),
            content_padding=ft.padding.symmetric(vertical=self.scale_func(10), horizontal=self.scale_func(3)),
            on_change=self._on_field_change
        )

        self.change_indicator = ft.Icon(ft.Icons.EDIT, color=ft.Colors.ORANGE, size=self.scale_func(20), visible=False)
        self.save_indicator = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=self.scale_func(20), visible=False)
        self.date_error_indicator = ft.Icon(ft.Icons.ERROR, color=ft.Colors.ERROR, size=self.scale_func(20), visible=False)

        self.date_error_text = ft.Text("Start date cannot be after end date", color=ft.Colors.ERROR, size=self.scale_func(self.base_font_size), visible=False)

        self.save_btn = ft.IconButton(icon=ft.Icons.SAVE, tooltip="Save", on_click=self.save)
        self.delete_btn = ft.IconButton(icon=ft.Icons.DELETE, tooltip="Delete", on_click=self.delete)
        self.duplicate_btn = ft.IconButton(icon=ft.Icons.CONTENT_COPY, tooltip="Duplicate", on_click=self.duplicate, disabled=self.db_id is None)
        self.attach_btn = ft.IconButton(icon=ft.Icons.ATTACH_FILE, tooltip="Attach files", on_click=self._attach_file, disabled=self.db_id is None)
        self.move_up_btn = ft.IconButton(icon=ft.Icons.ARROW_UPWARD, on_click=self._move_up, tooltip="Move up")
        self.move_down_btn = ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD, on_click=self._move_down, tooltip="Move down")
        self.minimize_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            tooltip="Minimize",
            on_click=self._toggle_minimize,
            rotate=ft.Rotate(0),
            animate_rotation=ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_IN_OUT)
        )

        self.reorder_arrows_col = ft.Container(
            content=ft.Column(
                [self.move_up_btn, self.move_down_btn], 
                spacing=0),
            width=0,
            animate=ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_OUT),
            clip_behavior=ft.ClipBehavior.HARD_EDGE
        )

        # Cabeçalho da task com botão de minimizar
        self.task_header = ft.Row([
            self.display_id_text,
            self.title_field,
            self.minimize_btn
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Conteúdo expandível da task
        indicators_row = ft.Row([self.change_indicator, self.save_indicator, self.date_error_indicator], spacing=self.scale_func(5))
        details_row = ft.Row(
            [
                self.start_date_container,
                self.end_date_container,
                self.priority_field,
                self.status_field,
            ], spacing=self.scale_func(12), vertical_alignment=ft.CrossAxisAlignment.END
        )

        action_buttons_footer = ft.Container(
            content=ft.Row(
                [indicators_row, ft.Container(expand=True), self.attach_btn, self.duplicate_btn, self.save_btn, self.delete_btn],
                spacing=self.scale_func(5)
            ),
            padding=ft.padding.only(top=self.scale_func(10)),
            border=ft.border.only(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)))
        )

        # This column grows instantly when typing, without animation.
        inner_expandable_content = ft.Column([
            self.task_field,
            self.checklist_col,
            ft.Row([self.add_checklist_item_btn]),
            details_row,
            self.date_error_text, 
            self.drop_zone,
            self.attachments_list,
            action_buttons_footer,
        ],
        spacing=self.scale_func(12))

        # This container wraps the content and provides the open/close animation.
        self.expandable_content = ft.Container(
            content=inner_expandable_content,
            animate_opacity=ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_OUT),
            clip_behavior=ft.ClipBehavior.HARD_EDGE
        )
        
        # Conteúdo minimizado - apenas informações essenciais
        self.attachment_count = 0
        self.minimized_dates_text = ft.Text("", size=self.scale_func(self.base_font_size), color=ft.Colors.ON_SURFACE_VARIANT)
        self.minimized_attachments_text = ft.Text("", size=self.scale_func(self.base_font_size + 2), color=ft.Colors.PRIMARY)
        self.minimized_due_date_info = ft.Row(
            [
                ft.Icon(ft.Icons.ALARM, size=self.scale_func(12)),
                ft.Text("", size=self.scale_func(self.base_font_size), weight=ft.FontWeight.BOLD)
            ],
            visible=False,
            spacing=self.scale_func(4),
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        self.minimized_priority_info = ft.Row(
            [
                ft.Icon(size=self.scale_func(14)),
                ft.Text("", size=self.scale_func(self.base_font_size), weight=ft.FontWeight.BOLD)
            ],
            visible=False,
            spacing=self.scale_func(4),
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        self.minimized_info = ft.Row([
            self.minimized_dates_text,
            self.minimized_attachments_text,
            self.minimized_due_date_info,
            self.minimized_priority_info,
            ft.Container(expand=True),
        ], spacing=self.scale_func(15), vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.task_main_content = ft.Column([
            self.task_header,
            self.expandable_content,
            self.minimized_info
        ], spacing=self.scale_func(15), expand=True)

        # Container principal da task
        self.main_container = ft.Container(
            content=ft.Row(
                [self.reorder_arrows_col, self.task_main_content],
                vertical_alignment=ft.CrossAxisAlignment.START
            ),
            padding=self.scale_func(20),
            border_radius=self.scale_func(20),
            margin=ft.margin.only(bottom=self.scale_func(10)),
            animate=ft.Animation(duration=300, curve="ease"),
            ink=True,
            on_click=lambda e: None
        )

        # Wrap in a file drop target
        super().__init__(
            content=ft.DragTarget(
                group="files",
                content=self.main_container,
                on_will_accept=self._on_drag_will_accept,
                on_accept=self._on_drag_accept,
                on_leave=self._on_drag_leave,
            ),
            opacity=0,
            animate_opacity=ft.Animation(duration=400, curve="ease_in")
        )

        if self.db_id:
            self._load_attachments()
        self._load_checklist()
        self._on_status_change()
        self._validate_dates()
        self._update_minimized_info()
        self.set_minimized(True, animated=False)

    def update_theme_colors(self):
        if not self.page or not self.page.app_instance:
            return

        # Fallback for older Flet versions that don't have `effective_theme`
        current_theme = None
        if hasattr(self.page, 'effective_theme') and self.page.effective_theme:
            current_theme = self.page.effective_theme
        else:
            current_theme = self.page.dark_theme if self.page.theme_mode == ft.ThemeMode.DARK else self.page.theme

        if not current_theme or not current_theme.color_scheme:
            return # Cannot determine Colors

        # Usa surface_variant para o fundo do card
        new_bgcolor = current_theme.color_scheme.surface_variant

        # Verifica se a cor atual é uma cor de notificação antes de sobrescrever
        is_notification_color = self.main_container.bgcolor and self.main_container.bgcolor not in [self.original_bgcolor, None]
        
        self.original_bgcolor = new_bgcolor
        if not is_notification_color:
            self.main_container.bgcolor = self.original_bgcolor
        
        self._update_minimized_info()
        
        try: self.update() 
        except: pass

    def update_font_sizes(self):
        """Updates font sizes for all relevant controls in the task."""
        self.base_font_size = self.page.app_instance.base_font_size
        
        self.task_field.text_style.size = self.scale_func(self.base_font_size)
        self.start_date_field.text_style.size = self.scale_func(self.base_font_size)
        self.end_date_field.text_style.size = self.scale_func(self.base_font_size)
        self.status_field.text_style.size = self.scale_func(self.base_font_size)
        self.priority_field.text_style.size = self.scale_func(self.base_font_size)
        self.date_error_text.size = self.scale_func(self.base_font_size)
        self.minimized_dates_text.size = self.scale_func(self.base_font_size)
        self.minimized_attachments_text.size = self.scale_func(self.base_font_size + 2)
        self.minimized_due_date_info.controls[1].size = self.scale_func(self.base_font_size)
        self.minimized_priority_info.controls[1].size = self.scale_func(self.base_font_size)
        # Attachments list fonts are updated on _load_attachments
        for item_row in self.checklist_col.controls:
            if isinstance(item_row, ft.Row) and len(item_row.controls) > 1:
                textfield = item_row.controls[1]
                if isinstance(textfield, ft.TextField):
                    textfield.text_style.size = self.scale_func(self.base_font_size)
        try: self.update()
        except: pass

    def _move_up(self, e):
        if self.on_move_up:
            self.on_move_up(self)

    def _move_down(self, e):
        if self.on_move_down:
            self.on_move_down(self)

    def _toggle_minimize(self, e):
        self.set_minimized(not self.is_minimized, animated=True)

    def _on_date_field_hover(self, e, icon_button):
        icon_button.opacity = 1 if e.data == "true" else 0
        try:
            icon_button.update()
        except:
            pass

    def set_minimized(self, minimized: bool, animated: bool = True):
        self.is_minimized = minimized

        if animated:
            self.expandable_content.animate_size = ft.Animation(duration=250, curve=ft.AnimationCurve.DECELERATE)
        else:
            self.expandable_content.animate_size = None

        if self.is_minimized:
            # Minimizar
            self.expandable_content.height = 0
            self.expandable_content.opacity = 0
            self.minimized_info.visible = True
            self.minimize_btn.rotate.angle = math.pi
            self.minimize_btn.tooltip = "Maximize"
        else:
            # Maximizar
            self.expandable_content.height = None
            self.expandable_content.opacity = 1
            self.minimized_info.visible = False
            self.minimize_btn.rotate.angle = 0
            self.minimize_btn.tooltip = "Minimize"
        
        try:
            self.update()
        except:
            pass

        # If we animated and opened the task, disable size animation afterwards
        # so that content changes (typing, adding items) don't animate.
        if animated and not self.is_minimized:
            def remove_animation_after_delay():
                time.sleep(0.3) # A bit longer than the animation duration
                self.expandable_content.animate_size = None
                try: self.update()
                except: pass
            threading.Thread(target=remove_animation_after_delay, daemon=True).start()

    def _create_checklist_item_row(self, item_id=None, text="", is_checked=False):
        item_row = ft.Row(
            data=item_id, # Store the DB id here
            controls=[
                ft.Checkbox(value=is_checked, on_change=self._on_checklist_change),
                ft.TextField(
                    value=text,
                    expand=True,
                    border=ft.InputBorder.UNDERLINE,
                    text_style=ft.TextStyle(size=self.scale_func(self.base_font_size)),
                    on_change=self._on_checklist_change
                ),
                ft.IconButton(
                    icon=ft.Icons.REMOVE,
                    icon_size=16,
                    on_click=self._delete_checklist_item_ui
                )
            ]
        )
        return item_row

    def _on_checklist_change(self, e=None):
        self.checklist_changed = True
        self._on_field_change()

    def _delete_checklist_item_ui(self, e):
        item_row = e.control.parent
        item_id = item_row.data
        if item_id:
            db.delete_checklist_item(item_id)
        self.checklist_col.controls.remove(item_row)
        self._on_checklist_change()
        try: self.update()
        except: pass

    def _add_checklist_item_ui(self, e=None):
        if not self.db_id:
            if hasattr(self, 'page') and self.page:
                self.page.snack_bar = ft.SnackBar(ft.Text("Please save the task before adding checklist items."), bgcolor=ft.Colors.ORANGE_400)
                self.page.snack_bar.open = True
                self.page.update()
            return
        new_item_row = self._create_checklist_item_row()
        self.checklist_col.controls.append(new_item_row)
        self._on_checklist_change()
        try: self.update()
        except: pass

    def _load_checklist(self):
        self.checklist_col.controls.clear()
        if not self.db_id: return
        items = db.list_checklist_items(self.db_id)
        for item in items:
            item_row = self._create_checklist_item_row(item['id'], item['text'], item['is_checked'])
            self.checklist_col.controls.append(item_row)
        try: self.update()
        except: pass

    def _save_checklist(self):
        if not self.checklist_changed or not self.db_id: return
        for item_row in self.checklist_col.controls:
            item_id, is_checked, text = item_row.data, item_row.controls[0].value, item_row.controls[1].value
            if item_id: db.update_checklist_item(item_id, text, is_checked)
            else: item_row.data = db.add_checklist_item(self.db_id, text, is_checked)
        self.checklist_changed = False

    def set_reorder_mode(self, active: bool):
        self.reorder_arrows_col.width = self.scale_func(40) if active else 0
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

        priority = self.priority_field.value
        priority_icon_control = self.minimized_priority_info.controls[0]
        priority_text_control = self.minimized_priority_info.controls[1]

        if priority:
            self.minimized_priority_info.visible = True
            priority_text_control.value = priority
            
            is_light_theme = self.page and self.page.theme_mode == ft.ThemeMode.LIGHT

            if priority == "Critical":
                color = ft.Colors.RED_700 if is_light_theme else ft.Colors.RED_400
                priority_icon_control.name = ft.Icons.KEYBOARD_DOUBLE_ARROW_UP
            elif priority == "Not Urgent":
                color = ft.Colors.GREEN_700 if is_light_theme else ft.Colors.GREEN_400
                priority_icon_control.name = ft.Icons.KEYBOARD_DOUBLE_ARROW_DOWN
            else: # Normal
                color = ft.Colors.BLUE_700 if is_light_theme else ft.Colors.BLUE_400
                priority_icon_control.name = ft.Icons.KEYBOARD_ARROW_RIGHT
            
            priority_icon_control.color = color
            priority_text_control.color = color
        else:
            self.minimized_priority_info.visible = False

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
                task_attachment_dir = os.path.join(ATTACHMENTS_DIR, str(self.db_id))
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

        task_attachment_dir = os.path.join(ATTACHMENTS_DIR, str(self.db_id))
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
        self.date_error_indicator.visible = True # Este ícone já usa a cor do tema
        self.date_error_text.visible = True # Este texto já usa a cor do tema
        self.save_btn.disabled = True
        self.start_date_field.border_color = ft.Colors.ERROR
        self.end_date_field.border_color = ft.Colors.ERROR
        try: self.update()
        except: pass

    def _clear_date_error(self):
        self.has_date_error = False
        self.date_error_indicator.visible = False # Este ícone já usa a cor do tema
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
        return self.attachments_changed or self.checklist_changed

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
        self.checklist_changed = False

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
                ft.Row([ # The text size here will be updated when update_font_sizes is called, as _load_attachments is called inside it.
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
        self.set_minimized(False, animated=True)
        self.scroll_to(duration=1000, curve=ft.AnimationCurve.EASE_IN_OUT)

    def _get_due_color(self, days_diff):
        is_light_theme = self.page and self.page.theme_mode == ft.ThemeMode.LIGHT

        if days_diff < 0:
            return ft.Colors.RED_700 if is_light_theme else ft.Colors.RED_400
        if days_diff > 3:
            return ft.Colors.ORANGE_700 if is_light_theme else ft.Colors.ORANGE_400

        # Use darker shades for light theme for better contrast
        orange = (245, 124, 0) if is_light_theme else (255, 167, 38)  # ORANGE_700 vs ORANGE_400
        red = (211, 47, 47) if is_light_theme else (239, 83, 80)      # RED_700 vs RED_400
        
        factor = (3 - days_diff) / 3.0
        
        r = int(orange[0] + (red[0] - orange[0]) * factor)
        g = int(orange[1] + (red[1] - orange[1]) * factor)
        b = int(orange[2] + (red[2] - orange[2]) * factor)
        
        return f"#{r:02x}{g:02x}{b:02x}"

    def set_notification_status(self, status, days_diff=None):
        self.notification_status = status
        if status == "overdue":
            self.minimized_due_date_info.visible = True
            is_light_theme = self.page and self.page.theme_mode == ft.ThemeMode.LIGHT
            color = ft.Colors.RED_700 if is_light_theme else ft.Colors.RED_400
            self.minimized_due_date_info.controls[0].color = color
            self.minimized_due_date_info.controls[1].value = f"{-days_diff}d overdue"
            self.minimized_due_date_info.controls[1].color = color
        elif status == "upcoming":
            self.minimized_due_date_info.visible = True
            color = self._get_due_color(days_diff)
            self.minimized_due_date_info.controls[0].color = color
            self.minimized_due_date_info.controls[1].value = f"in {days_diff}d"
            self.minimized_due_date_info.controls[1].color = color
        else:  # None
            if self.original_bgcolor:
                self.main_container.bgcolor = self.original_bgcolor
            self.minimized_due_date_info.visible = False
        
        try: self.update()
        except: pass

    def did_mount(self):
        self.opacity = 1 # Fade in
        if hasattr(self, 'page') and self.page:
            self.update_theme_colors()
            try:
                self.page.overlay.append(self.start_date_picker)
                self.page.overlay.append(self.end_date_picker)
                self.page.overlay.append(self.file_picker)
                self.update() # To start the fade-in animation
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
        is_light_theme = self.page and self.page.theme_mode == ft.ThemeMode.LIGHT

        if v == "ongoing":
            self.status_field.color = ft.Colors.ORANGE_700 if is_light_theme else "#FFA726"  # Orange 400
        elif v == "complete":
            self.status_field.color = ft.Colors.GREEN_700 if is_light_theme else "#66BB6A"  # Green 400
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
        self._save_checklist()
        self.on_save(self, self.get_data())
        self._update_original_data()
        self.attachments_changed = False
        self._show_save_indicator()
        
        if hasattr(self.page, 'app_instance'):
            self.page.app_instance.check_all_due_dates()

    def delete(self, e=None):
        self.on_delete(self)

    def duplicate(self, e=None):
        self.on_duplicate(self)

# ---- EditableTabLabel e dialogs ----
class EditableTabLabel(ft.Row):
    def __init__(self, text, on_rename, scale_func, base_font_size=12):
        super().__init__(alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
        self.scale_func = scale_func
        self.base_font_size = base_font_size; self.text = text; self.on_rename = on_rename
        self.display_text = ft.Text(self.text, size=self.scale_func(self.base_font_size + 2), weight=ft.FontWeight.BOLD)
        self.clickable_text = ft.GestureDetector(content=self.display_text, on_double_tap=self.start_editing)
        self.edit_field = ft.TextField(value=self.text, border="none", read_only=False, width=self.scale_func(120), on_submit=self.finish_editing, on_blur=self.finish_editing)
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

    def update_font_sizes(self):
        self.display_text.size = self.scale_func(self.base_font_size + 2)
        try: self.update()
        except: pass

class DeleteConfirmationDialog(ft.AlertDialog):
    def __init__(self, on_confirm, on_cancel, scale_func):
        super().__init__()
        self.on_confirm = on_confirm; self.on_cancel = on_cancel
        self.scale_func = scale_func
        self.confirmation_text = ft.TextField(width=self.scale_func(300)); self.title = ft.Text()
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
    def __init__(self, on_confirm, on_cancel, scale_func):
        super().__init__()
        self.on_confirm = on_confirm; self.on_cancel = on_cancel; self.random_code = ""
        self.scale_func = scale_func
        self.confirmation_text = ft.TextField(width=self.scale_func(300)); self.title = ft.Text("Delete task?")
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
    def __init__(self, on_auto_save_toggle, initial_value, on_close, on_dpi_change, initial_dpi_scale, on_theme_change, initial_theme, scale_func, version, on_font_size_change, initial_font_size, on_carousel_settings_change, initial_carousel_show_progress, initial_carousel_speed, on_translucency_change, initial_translucency_enabled, initial_translucency_level):
        super().__init__()
        self.on_auto_save_toggle = on_auto_save_toggle
        self.on_close = on_close
        self.on_dpi_change = on_dpi_change
        self.on_theme_change = on_theme_change
        self.on_font_size_change = on_font_size_change
        self.on_carousel_settings_change = on_carousel_settings_change
        self.on_translucency_change = on_translucency_change
        self.scale_func = scale_func
        self.version = version
        self.base_font_size = initial_font_size

        self.title = ft.Text("Settings")
        self.auto_save_checkbox = ft.Checkbox(
            label="Auto save changes on tasks",
            value=initial_value,
            on_change=self.on_auto_save_toggle
        )

        dpi_options = {
            "Auto (Recommended)": "0.0",
            "50%": "0.5",
            "60%": "0.6",
            "70%": "0.7",
            "80%": "0.8",
            "90%": "0.9",
            "100%": "1.0",
            "110%": "1.1",
            "120%": "1.2",
            "130%": "1.3",
            "140%": "1.4",
            "150%": "1.5",
        }
        # The value from the DB is already a string (e.g., "0.0", "1.0")
        initial_dpi_value = initial_dpi_scale

        self.dpi_dropdown = ft.Dropdown(
            label="Display Scaling (requires restart)",
            options=[ft.dropdown.Option(key=v, text=k) for k, v in dpi_options.items()],
            value=initial_dpi_value,
            on_change=self._handle_dpi_change,
            expand=True
        )

        self.theme_dropdown = ft.Dropdown(
            label="Theme",
            options=[
                ft.dropdown.Option("Dracula"),
                ft.dropdown.Option("Dark"),
                ft.dropdown.Option("Light"),
            ],
            value=initial_theme,
            on_change=self.on_theme_change,
            expand=True
        )

        self.font_size_dropdown = ft.Dropdown(
            label="Base Font Size",
            options=[ft.dropdown.Option(str(i)) for i in range(8, 21)],
            value=str(initial_font_size),
            on_change=self.on_font_size_change,
            expand=True
        )

        self.carousel_show_progress_checkbox = ft.Checkbox(
            label="Show progress bar in mini-view",
            value=initial_carousel_show_progress,
            on_change=self._handle_carousel_setting_change
        )

        self.carousel_speed_dropdown = ft.Dropdown(
            label="Mini-view rotation speed (seconds)",
            options=[ft.dropdown.Option(str(s)) for s in [3, 5, 8, 10, 15, 20]],
            value=str(initial_carousel_speed),
            on_change=self._handle_carousel_setting_change,
            expand=True
        )

        self.translucency_enabled_checkbox = ft.Checkbox(
            label="Enable mini-view translucency",
            value=initial_translucency_enabled,
            on_change=self._handle_translucency_change
        )

        self.translucency_slider = ft.Slider(
            min=20,
            max=100,
            divisions=8,
            value=initial_translucency_level,
            label="{value}% opacity",
            on_change_end=self._handle_translucency_change,
            disabled=not initial_translucency_enabled
        )

        self.version_text = ft.Text(
            f"Version {self.version}",
            size=self.scale_func(self.base_font_size - 2),
            color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.RIGHT
        )

        self.content = ft.Column(
            [
                self.auto_save_checkbox, self.dpi_dropdown, self.theme_dropdown, self.font_size_dropdown,
                ft.Divider(),
                ft.Text("Mini-view Carousel", weight=ft.FontWeight.BOLD),
                self.carousel_show_progress_checkbox,
                self.carousel_speed_dropdown,
                ft.Divider(),
                ft.Text("Mini-view Appearance", weight=ft.FontWeight.BOLD),
                self.translucency_enabled_checkbox,
                self.translucency_slider,
                ft.Divider(height=self.scale_func(20)), 
                ft.Row([ft.Container(expand=True), self.version_text])
            ],
            tight=True, spacing=20
        )
        self.actions = [ft.TextButton("Close", on_click=self.close_dialog)]
        self.actions_alignment = ft.MainAxisAlignment.END

    def update_font_sizes(self):
        """Updates font sizes for controls inside the dialog."""
        self.version_text.size = self.scale_func(self.base_font_size - 2)
        try: self.update()
        except: pass

    def _handle_dpi_change(self, e):
        self.on_dpi_change(float(e.control.value))

    def _handle_translucency_change(self, e):
        # When checkbox is toggled, enable/disable slider
        is_enabled = self.translucency_enabled_checkbox.value
        self.translucency_slider.disabled = not is_enabled
        try:
            self.update()
        except:
            pass
        self.on_translucency_change()

    def _handle_carousel_setting_change(self, e):
        self.on_carousel_settings_change()

    def close_dialog(self, e):
        self.open = False
        self.on_close()

class MiniViewCarousel(ft.Container):
    def __init__(self, app, scale_func):
        self.app = app
        self.scale_func = scale_func
        self.current_tab_index = 0
        self._thread = None
        self._stop_event = threading.Event()

        # Initialize with a placeholder content
        super().__init__(
            width=scale_func(110),
            height=scale_func(110),
            alignment=ft.alignment.center,
            content=ft.Text("Loading...", size=scale_func(12)),
            visible=True,
            padding=scale_func(5),
            border_radius=scale_func(10),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLACK)
        )

    def _create_slide(self, tab_name_str, stats):
        """Creates the UI for a single slide."""
        tab_name = ft.Text(tab_name_str, weight=ft.FontWeight.BOLD, size=self.scale_func(12), text_align=ft.TextAlign.CENTER, no_wrap=True)
        
        show_progress = db.get_setting('carousel_show_progress', 'True') == 'True'
        progress_bar = ft.ProgressBar(bar_height=self.scale_func(6), expand=True, value=stats.get("progress", 0), visible=show_progress)
        
        total_tasks = self._create_stat_display(ft.Icons.FUNCTIONS, ft.Colors.BLUE, "Total Tasks", stats.get("total", "0"))
        ongoing_tasks = self._create_stat_display(ft.Icons.LOOP, ft.Colors.ORANGE, "Ongoing", stats.get("ongoing", "0"))
        completed_tasks = self._create_stat_display(ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.GREEN, "Complete", stats.get("completed", "0"))
        overdue_tasks = self._create_stat_display(ft.Icons.ERROR_OUTLINE, ft.Colors.RED, "Overdue", stats.get("overdue", "0"))

        return ft.Column(
            [
                tab_name,
                ft.Container(progress_bar, padding=ft.padding.symmetric(vertical=self.scale_func(1))),
                ft.Row(
                    [total_tasks, ongoing_tasks, completed_tasks, overdue_tasks],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=self.scale_func(3)
        )

    def _create_stat_display(self, icon, color, tooltip, value):
        return ft.Column(
            [
                ft.Icon(icon, color=color, size=self.scale_func(14), tooltip=tooltip),
                ft.Text(str(value), size=self.scale_func(11), weight=ft.FontWeight.BOLD)
            ],
            spacing=self.scale_func(2),
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def did_mount(self):
        """Start the carousel thread once the control is mounted on the page."""
        self.start_carousel()

    def start_carousel(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop_carousel(self):
        self._stop_event.set()

    def _run(self):
        time.sleep(2)
        while not self._stop_event.is_set():
            try:
                if self.app and self.app.page and self.visible:
                    # Check for run_threadsafe for compatibility with older Flet versions
                    if hasattr(self.app.page, "run_threadsafe"):
                        self.app.page.run_threadsafe(self.update_display)
                    else:
                        # Fallback for older Flet. This is not thread-safe and might be unstable.
                        self.update_display()

                speed = int(db.get_setting('carousel_speed', '5'))
                self._stop_event.wait(speed)
            except Exception as e:
                print(f"Error in MiniViewCarousel thread: {e}")
                time.sleep(5)

    def update_display(self):
        """
        This method runs entirely in the UI thread.
        It safely reads data from other controls and updates its own UI.
        """
        if not self.app.tabs.tabs or not len(self.app.tabs.tabs):
            self.content = ft.Text("No Tabs", size=self.scale_func(12))
            try: self.update()
            except: pass
            return

        num_tabs = len(self.app.tabs.tabs)
        if self.current_tab_index >= num_tabs:
            self.current_tab_index = 0
        
        # Find the next valid AgendaTab to display
        start_index = self.current_tab_index
        agenda_tab = None
        while True:
            current_tab_control = self.app.tabs.tabs[self.current_tab_index]
            if isinstance(current_tab_control.content, AgendaTab):
                agenda_tab = current_tab_control.content
                break
            
            self.current_tab_index = (self.current_tab_index + 1) % num_tabs
            if self.current_tab_index == start_index:
                # Cycled through all tabs, none are valid
                self.content = ft.Text("No valid tabs", size=self.scale_func(12))
                try: self.update()
                except: pass
                return

        # --- Get stats from the AgendaTab's overview controls ---
        stats = {
            "total": agenda_tab.overview_total_tasks.value,
            "ongoing": agenda_tab.overview_ongoing_tasks.value,
            "completed": agenda_tab.overview_completed_tasks.value,
            "overdue": agenda_tab.overview_overdue_tasks.value,
            "progress": agenda_tab.overview_completion_progress.value,
        }
        tab_name_str = agenda_tab.tab_name

        # Create the new slide UI and replace the content
        new_slide = self._create_slide(tab_name_str, stats)
        self.content = new_slide
        
        # Move to the next index for the next cycle
        self.current_tab_index = (self.current_tab_index + 1)

        try:
            self.update()
        except Exception:
            pass

# ---- AgendaTab ----
class AgendaTab(ft.Column):
    PRIORITY_ORDER = {"Critical": 0, "Normal": 1, "Not Urgent": 2}

    def __init__(self, tab_name, on_delete_tab_request, page, delete_dialog, get_auto_save_setting, scale_func, base_font_size):
        self.tab_name = tab_name
        self.on_delete_tab_request = on_delete_tab_request
        self.page = page
        self.delete_dialog = delete_dialog
        self.reorder_mode_active = False
        self.base_font_size = base_font_size

        # ListView simples sem DragTarget para tasks
        self.get_auto_save_setting = get_auto_save_setting
        self.scale_func = scale_func # Store scale function
        self.ongoing_list = ft.ListView(expand=True, spacing=self.scale_func(10), padding=self.scale_func(10))
        self.complete_list = ft.ListView(expand=True, spacing=self.scale_func(10), padding=self.scale_func(10))

        # --- Controles para a aba Overview ---
        self.overview_total_tasks = ft.Text("0", weight=ft.FontWeight.BOLD, size=self.scale_func(28))
        self.overview_ongoing_tasks = ft.Text("0", weight=ft.FontWeight.BOLD, size=self.scale_func(28), color=ft.Colors.ORANGE)
        self.overview_completed_tasks = ft.Text("0", weight=ft.FontWeight.BOLD, size=self.scale_func(28), color=ft.Colors.GREEN)
        self.overview_overdue_tasks = ft.Text("0", weight=ft.FontWeight.BOLD, size=self.scale_func(28), color=ft.Colors.RED)
        self.overview_completion_progress = ft.ProgressBar(value=0, bar_height=self.scale_func(10), expand=True)
        self.overview_completion_percent = ft.Text("0%", weight=ft.FontWeight.BOLD)

        self.total_card = self._create_stat_card("Total Tasks", self.overview_total_tasks, ft.Icons.FUNCTIONS, ft.Colors.BLUE)
        self.ongoing_card = self._create_stat_card("Ongoing", self.overview_ongoing_tasks, ft.Icons.LOOP, ft.Colors.ORANGE)
        self.completed_card = self._create_stat_card("Completed", self.overview_completed_tasks, ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.GREEN)
        self.overdue_card = self._create_stat_card("Overdue", self.overview_overdue_tasks, ft.Icons.ERROR_OUTLINE, ft.Colors.RED)

        self.overview_content = ft.Container(
            ft.Column([
                ft.Row([self.total_card, self.ongoing_card], spacing=self.scale_func(15)),
                ft.Row([self.completed_card, self.overdue_card], spacing=self.scale_func(15)),
                ft.Divider(height=self.scale_func(30)),
                ft.Text("Completion Progress", style=ft.TextThemeStyle.TITLE_MEDIUM),
                ft.Container(
                    content=ft.Row([
                        self.overview_completion_progress,
                        self.overview_completion_percent
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=self.scale_func(10)),
                    padding=ft.padding.only(top=self.scale_func(10))
                ),
            ], spacing=self.scale_func(15)),
            padding=self.scale_func(20),
            expand=True
        )

        self.task_to_delete = None
        self.delete_task_dialog = DeleteTaskConfirmationDialog(on_confirm=self.confirm_delete_task, on_cancel=self.cancel_delete_task, scale_func=self.scale_func)

        self.inner_tabs = ft.Tabs(
            tabs=[
                ft.Tab(text="Overview", content=self.overview_content),
                ft.Tab(text="Ongoing", content=ft.Container(self.ongoing_list, expand=True, padding=self.scale_func(10))),
                ft.Tab(text="Complete", content=ft.Container(self.complete_list, expand=True, padding=self.scale_func(10)))
            ],
            expand=True,
            selected_index=1 # Começa na aba "Ongoing"
        )

        self.reorder_mode_btn = ft.IconButton(
            icon=ft.Icons.SWAP_VERT,
            tooltip="Enable reordering",
            on_click=self.toggle_reorder_mode,
            rotate=ft.Rotate(0),
            animate_rotation=ft.Animation(duration=400, curve=ft.AnimationCurve.EASE_IN_OUT)
        )
        self.toggle_all_tasks_btn = ft.IconButton(
            icon=ft.Icons.UNFOLD_MORE,
            tooltip="Maximize All",
            on_click=self.toggle_all_tasks
        )
        self.add_task_btn = ft.ElevatedButton(text="Add Task", icon=ft.Icons.ADD, on_click=self.add_task)
        self.delete_tab_btn = ft.IconButton(icon=ft.Icons.DELETE, tooltip="Delete Tab", on_click=lambda e: self.on_delete_tab_request(self.tab_name))
        self.buttons_row = ft.Row([self.reorder_mode_btn, self.toggle_all_tasks_btn, ft.Container(expand=True), self.add_task_btn, self.delete_tab_btn], alignment=ft.MainAxisAlignment.END, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=self.scale_func(10))

        super().__init__(spacing=self.scale_func(12), expand=True, controls=[self.inner_tabs, self.buttons_row])

    def _create_stat_card(self, title: str, value_control: ft.Control, icon: str, icon_color: str):
        value_control.text_align = ft.TextAlign.RIGHT
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=icon_color, size=self.scale_func(18)),
                            ft.Text(title, weight=ft.FontWeight.BOLD, size=self.scale_func(self.base_font_size)),
                        ],
                        spacing=self.scale_func(8),
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Container(
                        content=value_control,
                        alignment=ft.alignment.center_right,
                        padding=ft.padding.only(top=self.scale_func(10)),
                    ),
                ],
                spacing=self.scale_func(5),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=self.scale_func(15),
            border_radius=self.scale_func(10),
            expand=True,
            ink=True,
            on_click=lambda e: None,
            height=self.scale_func(110)
        )

    def did_mount(self):
        self.update_theme_colors()

    def update_theme_colors(self):
        if not self.page:
            return

        # Fallback for older Flet versions that don't have `effective_theme`
        current_theme = None
        if hasattr(self.page, 'effective_theme') and self.page.effective_theme:
            current_theme = self.page.effective_theme
        else:
            current_theme = self.page.dark_theme if self.page.theme_mode == ft.ThemeMode.DARK else self.page.theme

        if not current_theme or not current_theme.color_scheme:
            return

        card_bgcolor = current_theme.color_scheme.surface_variant
        
        self.total_card.bgcolor = card_bgcolor
        self.ongoing_card.bgcolor = card_bgcolor
        self.completed_card.bgcolor = card_bgcolor
        self.overdue_card.bgcolor = card_bgcolor
        
        try:
            self.overview_content.update()
        except:
            pass

    def update_font_sizes(self):
        """Updates font sizes for this tab and all its tasks."""
        self.base_font_size = self.page.app_instance.base_font_size

        # Update stat card titles
        for card in [self.total_card, self.ongoing_card, self.completed_card, self.overdue_card]:
            title_text = card.content.controls[0].controls[1]
            title_text.size = self.scale_func(self.base_font_size)

        # Update tasks
        for task_list in [self.ongoing_list, self.complete_list]:
            for task in task_list.controls:
                if isinstance(task, TaskRow):
                    task.update_font_sizes()
        try: self.update()
        except: pass

    def update_overview_stats(self):
        ongoing_tasks = self.ongoing_list.controls
        completed_tasks = self.complete_list.controls
        all_tasks = ongoing_tasks + completed_tasks

        total_count = len(all_tasks)
        ongoing_count = len(ongoing_tasks)
        completed_count = len(completed_tasks)
        overdue_count = sum(1 for task in ongoing_tasks if isinstance(task, TaskRow) and task.notification_status == "overdue")
        
        completion_percentage = (completed_count / total_count) if total_count > 0 else 0

        self.overview_total_tasks.value = str(total_count)
        self.overview_ongoing_tasks.value = str(ongoing_count)
        self.overview_completed_tasks.value = str(completed_count)
        self.overview_overdue_tasks.value = str(overdue_count)
        self.overview_completion_progress.value = completion_percentage
        self.overview_completion_percent.value = f"{completion_percentage:.0%}"

        try: self.overview_content.update()
        except: pass

    def toggle_reorder_mode(self, e):
        self.reorder_mode_active = not self.reorder_mode_active
        
        if self.reorder_mode_active:
            self.reorder_mode_btn.icon = ft.Icons.LOCK
            self.reorder_mode_btn.tooltip = "Disable reordering (lock order)"
            self.reorder_mode_btn.icon_color = ft.Colors.AMBER
            self.reorder_mode_btn.rotate.angle += math.pi * 2
        else:
            self.reorder_mode_btn.icon = ft.Icons.SWAP_VERT
            self.reorder_mode_btn.tooltip = "Enable reordering"
            self.reorder_mode_btn.icon_color = None
            self.reorder_mode_btn.rotate.angle -= math.pi * 2

        all_tasks = self.ongoing_list.controls + self.complete_list.controls
        for task in all_tasks:
            if isinstance(task, TaskRow):
                task.set_reorder_mode(self.reorder_mode_active)
                # Minimiza todas as tarefas ao entrar no modo de reordenação
                if self.reorder_mode_active:
                    task.set_minimized(True, animated=True)
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
            task.set_minimized(should_minimize, animated=True)

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
            row = TaskRow(self.on_save_task, self.on_delete_task, self.on_duplicate_task, self.on_move_task_up, self.on_move_task_down, title=t["title"], task=t["task"], start_date=t["start_date"], end_date=t["end_date"], status=t["status"], priority=t["priority"], db_id=t["id"], get_auto_save_setting=self.get_auto_save_setting, scale=self.scale_func, base_font_size=self.base_font_size)
            if t["status"] == "Ongoing":
                self.ongoing_list.controls.append(row)
            else:
                self.complete_list.controls.append(row)
        self.update_arrow_states()
        self.update_overview_stats()
        try: self.update()
        except: pass

    def add_task(self, e=None, data=None):
        row = TaskRow(
            on_save=self.on_save_task,
            on_delete=self.on_delete_task,
            on_duplicate=self.on_duplicate_task,
            on_move_up=self.on_move_task_up,
            on_move_down=self.on_move_task_down,
            get_auto_save_setting=self.get_auto_save_setting,
            scale=self.scale_func,
            base_font_size=self.base_font_size,
            **(data or {})
        )
        row.set_reorder_mode(self.reorder_mode_active)
        
        target_list = self.ongoing_list if row.status_field.value == "Ongoing" else self.complete_list
        target_list.controls.insert(0, row)

        self.update_overview_stats()
        self.update_arrow_states()
        # Don't auto-save duplicated tasks, let the caller handle it
        if (self.get_auto_save_setting and self.get_auto_save_setting()) and not data:
            row.save()
        # Update the entire tab to ensure the new row is rendered.
        try:
            self.page.update()
        except:
            pass
        return row

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

    def on_duplicate_task(self, original_task_row):
        data = original_task_row.get_data()
        data['title'] = f"{data.get('title', '')} (Copy)"

        # Create a new task row instance by reusing add_task
        new_row = self.add_task(data=data)

        # Save the new task to get a db_id and persist it
        new_row.save()

        # Now, duplicate checklist items and attachments if the original and new tasks have IDs
        if original_task_row.db_id and new_row.db_id:
            # Duplicate checklist items
            original_checklist_items = db.list_checklist_items(original_task_row.db_id)
            for item in original_checklist_items:
                db.add_checklist_item(new_row.db_id, item['text'], item['is_checked'])
            new_row._load_checklist()

            # Duplicate attachments
            original_attachments = db.list_attachments(original_task_row.db_id)
            if original_attachments:
                new_task_attachment_dir = os.path.join(ATTACHMENTS_DIR, str(new_row.db_id))
                os.makedirs(new_task_attachment_dir, exist_ok=True)
                for att in original_attachments:
                    source_path = att['file_path']
                    if os.path.exists(source_path):
                        file_name = os.path.basename(source_path)
                        dest_path = os.path.join(new_task_attachment_dir, file_name)
                        try:
                            shutil.copy(source_path, dest_path)
                            db.add_attachment(new_row.db_id, dest_path)
                        except Exception as e:
                            print(f"Error copying attachment during duplication: {e}")
                new_row._load_attachments()

        try:
            new_row.scroll_to(duration=500)
        except:
            pass

    def on_save_task(self, row, data):
        is_new_task = not row.db_id

        # Save or update the task in the database
        if is_new_task:
            row.db_id = db.add_task(self.tab_name, data["title"], data["task"], data["start_date"], data["end_date"], data["status"], data["priority"])
        else:
            db.update_task(row.db_id, data["title"], data["task"], data["start_date"], data["end_date"], data["status"], data["priority"], self.tab_name)

        # If it was a new task, update its UI now that it has a database ID
        if is_new_task and row.db_id:
            row.attach_btn.disabled = False
            row.duplicate_btn.disabled = False
            row.display_id_text.value = f"#{row.db_id}"
            row.display_id_text.visible = True
            try: row.update()
            except: pass

        # Check if the task is in the correct list ("Ongoing" vs "Complete") and move it if necessary.
        # This handles both existing tasks with a status change and new tasks that might have had their status changed before the first save.
        is_in_ongoing = row in self.ongoing_list.controls
        should_be_in_ongoing = data["status"] == "Ongoing"

        if (should_be_in_ongoing and not is_in_ongoing) or (not should_be_in_ongoing and is_in_ongoing):
            self.move_task(row)
        else:
            # If no move is needed, just update the overview stats and the tab UI.
            self.update_overview_stats()
            try: self.update()
            except: pass

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
        self.update_overview_stats()
        self.update_arrow_states()
        try: self.page.update()
        except: pass

    def cancel_delete_task(self):
        self.task_to_delete = None
        self.delete_task_dialog.open = False
        try: self.page.update()
        except: pass

    def move_task(self, row):
        # Determine source and target lists
        source_list = self.complete_list if row.status_field.value == "Ongoing" else self.ongoing_list
        target_list = self.ongoing_list if row.status_field.value == "Ongoing" else self.complete_list

        # Remove from the source list
        if row in source_list.controls:
            try:
                source_list.controls.remove(row)
            except ValueError:
                pass

        # Add to the top of the target list
        target_list.controls.insert(0, row)

        self.update_overview_stats()
        self.update_arrow_states()
        
        # Update both lists involved in the move
        try:
            source_list.update()
            target_list.update()
        except Exception:
            pass

    def on_task_status_change(self, row):
        self.move_task(row)
        self.on_save_task(row, row.get_data())

# ---- AgendaApp ----
class AgendaApp(ft.Column):
    def __init__(self, page):
        super().__init__(spacing=12, expand=True)
        self.page = page

        # Get DPI setting, default to "Auto" (0.0) for first run
        self.dpi_scale_setting = db.get_setting('dpi_scale', '0.0')

        if float(self.dpi_scale_setting) == 0.0:
            # If "Auto", calculate scale based on screen DPI
            self.dpi_scale = get_auto_dpi_scale()
        else:
            # Otherwise, use the fixed value
            self.dpi_scale = float(self.dpi_scale_setting)

        self.scale_func = lambda value: int(value * self.dpi_scale)

        self.tabs = ft.Tabs(selected_index=0, scrollable=True, expand=True)
        self.auto_save_enabled = db.get_setting('auto_save', 'False') == 'True'
        self.theme_name = db.get_setting('theme', 'Dracula')
        self.base_font_size = int(db.get_setting('font_size', '12'))
        self.carousel_show_progress = db.get_setting('carousel_show_progress', 'True') == 'True'
        self.carousel_speed = int(db.get_setting('carousel_speed', '5'))
        self.translucency_enabled = db.get_setting('translucency_enabled', 'False') == 'True'
        self.translucency_level = int(db.get_setting('translucency_level', '80'))
        self.settings_dialog = SettingsDialog(
            on_auto_save_toggle=self.toggle_auto_save,
            initial_value=self.auto_save_enabled,
            on_close=self.close_settings_dialog,
            on_dpi_change=self.change_dpi,
            initial_dpi_scale=self.dpi_scale_setting,
            on_theme_change=self.change_theme,
            initial_theme=self.theme_name,
            scale_func=self.scale_func,
            version=VERSION,
            on_font_size_change=self.change_font_size,
            initial_font_size=self.base_font_size,
            on_carousel_settings_change=self.change_carousel_settings,
            initial_carousel_show_progress=self.carousel_show_progress,
            initial_carousel_speed=self.carousel_speed,
            on_translucency_change=self.change_translucency_settings,
            initial_translucency_enabled=self.translucency_enabled,
            initial_translucency_level=self.translucency_level
        )
        self.delete_dialog = DeleteConfirmationDialog(on_confirm=self.delete_tab, on_cancel=self.close_delete_dialog, scale_func=self.scale_func)
        self.add_tab_btn = ft.ElevatedButton(text="New Tab", icon=ft.Icons.ADD, on_click=self.add_new_tab)
        
        self.settings_btn = ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="Settings", on_click=self.open_settings_dialog)
        self.pin_switch = ft.Switch(value=False, on_change=self.toggle_pin, tooltip="Pin window open")
        self.header = ft.Row([
            ft.Text(f"📝 {APP_NAME}", style=ft.TextThemeStyle.HEADLINE_SMALL),
            ft.Container(expand=True), 
            self.settings_btn, 
            self.pin_switch, self.add_tab_btn
        ])
        
        self.controls = [self.header, self.tabs]
        self.apply_theme(self.theme_name)
        self.start_notification_checker()

    def change_translucency_settings(self):
        is_enabled = self.settings_dialog.translucency_enabled_checkbox.value
        level = self.settings_dialog.translucency_slider.value

        db.set_setting('translucency_enabled', str(is_enabled))
        db.set_setting('translucency_level', str(int(level)))

        self.translucency_enabled = is_enabled
        self.translucency_level = int(level)

        # Apply the change immediately
        self.apply_translucency()

    def apply_translucency(self):
        is_mini_view = self.page.app_container.opacity == 0

        if is_mini_view and self.translucency_enabled:
            self.page.window.bgcolor = ft.Colors.TRANSPARENT
            self.page.window.opacity = self.translucency_level / 100.0
        else:
            # Full view, or mini-view without translucency, should be opaque
            self.page.window.bgcolor = None # Let Flet use the theme's background
            self.page.window.opacity = 1.0
        
        try:
            self.page.update() # Update the whole page to apply window changes
        except: pass

    def change_carousel_settings(self):
        show_progress = self.settings_dialog.carousel_show_progress_checkbox.value
        speed = self.settings_dialog.carousel_speed_dropdown.value
        
        db.set_setting('carousel_show_progress', str(show_progress))
        db.set_setting('carousel_speed', speed)

        self.carousel_show_progress = show_progress
        self.carousel_speed = int(speed)

    def change_font_size(self, e):
        """Handles font size changes from the settings dialog."""
        new_size = int(e.control.value)
        self.base_font_size = new_size
        db.set_setting('font_size', str(new_size))
        self.update_all_font_sizes()

    def update_all_font_sizes(self):
        """Propagates font size changes to all components."""
        for tab in self.tabs.tabs:
            if isinstance(tab.content, AgendaTab):
                tab.content.update_font_sizes()
            if isinstance(tab.tab_content, EditableTabLabel):
                tab.tab_content.base_font_size = self.base_font_size
                tab.tab_content.update_font_sizes()
        
        self.settings_dialog.base_font_size = self.base_font_size
        self.settings_dialog.update_font_sizes()
        self.page.update()

    def change_theme(self, e):
        theme_name = e.control.value
        db.set_setting('theme', theme_name)
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name):
        self.theme_name = theme_name

        page_transitions = ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.NONE,
            ios=ft.PageTransitionTheme.NONE,
            linux=ft.PageTransitionTheme.NONE,
            macos=ft.PageTransitionTheme.NONE,
            windows=ft.PageTransitionTheme.NONE,
        )

        if theme_name == "Light":
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.page.theme = ft.Theme(
                color_scheme=ft.ColorScheme(
                    primary=ft.Colors.BLUE,
                    background="#ffffff",
                    surface="#ffffff",
                    surface_variant="#e9ecef",  # Cor do card (mais escura)
                    on_background=ft.Colors.BLACK,
                    on_surface=ft.Colors.BLACK,
                    on_surface_variant=ft.Colors.BLACK,
                    error=ft.Colors.RED_700,
                    outline=ft.Colors.GREY_400,
                ),
                page_transitions=page_transitions,
            )
            # Fornece um tema escuro básico como fallback
            self.page.dark_theme = ft.Theme(color_scheme_seed="blue", page_transitions=page_transitions)
        elif theme_name == "Dark":
            self.page.theme_mode = ft.ThemeMode.DARK
            # Fornece um tema claro básico como fallback
            self.page.theme = ft.Theme(color_scheme_seed="blue", page_transitions=page_transitions)
            self.page.dark_theme = ft.Theme(
                color_scheme=ft.ColorScheme(
                    primary=ft.Colors.BLUE_300,
                    background="#1f2937",
                    surface="#1f2937",
                    surface_variant="#374151",  # Cor do card
                    on_background=ft.Colors.WHITE,
                    on_surface=ft.Colors.WHITE,
                    on_surface_variant=ft.Colors.WHITE,
                    error=ft.Colors.RED_400,
                    outline=ft.Colors.GREY_700,
                ),
                page_transitions=page_transitions,
            )
        elif theme_name == "Dracula":
            self.page.theme_mode = ft.ThemeMode.DARK
            self.page.theme = DRACULA_THEME
            self.page.dark_theme = DRACULA_THEME
        
        for tab in self.tabs.tabs:
            if isinstance(tab.content, AgendaTab):
                tab.content.update_theme_colors()
                for task_row in (tab.content.ongoing_list.controls + tab.content.complete_list.controls):
                    if isinstance(task_row, TaskRow):task_row.update_theme_colors()
        self.page.update()

    def toggle_auto_save(self, e):
        self.auto_save_enabled = e.control.value
        db.set_setting('auto_save', self.auto_save_enabled)

    def get_auto_save_setting(self):
        return self.auto_save_enabled

    def change_dpi(self, new_scale):
        db.set_setting('dpi_scale', new_scale)

        # Show a message that a restart is required
        self.page.snack_bar = ft.SnackBar(ft.Text("Please restart the application to apply the new scaling."), bgcolor=ft.Colors.BLUE)
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

        for tab in self.tabs.tabs:
            agenda_tab = tab.content
            if isinstance(agenda_tab, AgendaTab):
                for task_row in agenda_tab.ongoing_list.controls:
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
                agenda_tab.update_overview_stats()

    def toggle_pin(self, e):
        self.page.pinned = self.pin_switch.value
        if self.page.pinned:
            self.page.window.width = self.scale_func(650)
            self.page.window.height = self.scale_func(900)
            self.page.app_container.opacity = 1
            self.page.mini_icon.visible = False
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
            tab_content = AgendaTab(name, self.open_delete_dialog_request, self.page, self.delete_dialog, self.get_auto_save_setting, self.scale_func, self.base_font_size)
            editable_label = EditableTabLabel(name, self.rename_tab, self.scale_func, self.base_font_size)
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
        tab_content = AgendaTab(tab_name, self.open_delete_dialog_request, self.page, self.delete_dialog, self.get_auto_save_setting, self.scale_func, self.base_font_size)
        editable_label = EditableTabLabel(tab_name, self.rename_tab, self.scale_func, self.base_font_size)
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
    scale_func = app.scale_func
    page.window.width = scale_func(100)
    page.window.height = scale_func(100)

    # Hide window to prevent flicker during initial positioning
    page.window.opacity = 0
    page.update()

    page.app_container = ft.Container(content=app, expand=True, opacity=0, animate_opacity=None, padding=scale_func(15))
    
    # The old mini_icon is now the carousel
    page.mini_icon = MiniViewCarousel(app, scale_func)
    stack = ft.Stack(expand=True, controls=[page.app_container, page.mini_icon])
    page.add(stack)

    app.load_tabs()
    # Initial check on startup
    app.check_all_due_dates()
    # Apply initial translucency
    app.apply_translucency()
    # The carousel will start automatically via its did_mount method

    page.pinned = False

    def position_window():
        try:
            screen_w, screen_h = pyautogui.size()
            
            # Calculate desired position
            desired_left = screen_w - page.window.width - scale_func(50)
            desired_top = 10

            # Clamp values to ensure the window is always visible on screen
            left = max(0, min(desired_left, screen_w - page.window.width))
            top = max(0, min(desired_top, screen_h - page.window.height))

            page.window.left = left
            page.window.top = top
        except Exception as e:
            print(f"Could not calculate window position: {e}")
            # Fallback position
            page.window.left = 10
            page.window.top = 10

    def check_mouse():
        while True:
            try:
                if page.pinned:
                    time.sleep(0.1); continue
                
                mx, my = pyautogui.position()
                x0, y0 = page.window.left, page.window.top
                x1, y1 = x0 + page.window.width, y0 + page.window.height
                
                is_inside = x0 <= mx <= x1 and y0 <= my <= y1
                if getattr(page, "is_picker_open", False) or getattr(page, "is_file_picker_open", False):
                    is_inside = True

                app_is_visible = page.app_container.opacity == 1
                
                # Only act if the state (inside/outside) has changed
                if is_inside and not app_is_visible:
                    page.window.width = scale_func(650); page.window.height = scale_func(900)
                    page.app_container.opacity = 1; page.mini_icon.visible = False
                    app.apply_translucency() # Make window opaque
                    position_window(); page.update()
                elif not is_inside and app_is_visible:
                    # When mouse leaves, if settings is open, close it
                    if app.settings_dialog.open:
                        app.settings_dialog.open = False

                    page.window.width = scale_func(100); page.window.height = scale_func(100)
                    page.app_container.opacity = 0; page.mini_icon.visible = True
                    app.apply_translucency() # Apply translucency settings
                    position_window(); page.update()
                
                time.sleep(0.1)
            except Exception as e:
                print(f"Error in mouse checker thread: {e}"); time.sleep(0.5)

    # Position the window for the first time, then make it visible
    position_window()
    page.window.opacity = 1
    page.update()

    threading.Thread(target=check_mouse, daemon=True).start()

if __name__ == "__main__":
    ft.app(target=main)