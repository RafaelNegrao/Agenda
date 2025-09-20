import flet as ft
import sqlite3
from datetime import datetime
import pyautogui
import math
import threading
import time
import os
import shutil
import random
import sys
import string
import ctypes
import asyncio

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

def set_window_icon(page_title="TODO", icon_path="list.ico"):
    """
    Define o ícone da janela e da barra de tarefas usando a API do Windows.
    """
    try:
        # Constantes da API do Windows
        GWL_HICON = -14
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        
        # Carrega as bibliotecas necessárias
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # Encontra a janela pelo título - versões variadas para máxima compatibilidade
        possible_titles = [
            page_title,
            "Todo APP",
            "TODO",
            "Flet",  # Título padrão do Flet
            "main.py",  # Em modo debug
        ]
        
        hwnd = 0
        for title in possible_titles:
            hwnd = user32.FindWindowW(None, title)
            if hwnd != 0:
                break
        
        # Se não encontrou por título exato, busca por correspondência parcial
        if hwnd == 0:
            def enum_window_callback(hwnd, lParam):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    window_title = buffer.value.lower()
                    # Busca por qualquer título que contenha nossa aplicação
                    search_terms = ["todo", "agenda", "flet", "python"]
                    for term in search_terms:
                        if term in window_title:
                            found_windows.append(hwnd)
                            break
                return True
            
            found_windows = []
            enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(enum_proc(enum_window_callback), 0)
            
            if found_windows:
                hwnd = found_windows[0]
        
        # Busca pelo ícone em diferentes localizações possíveis
        icon_locations = [
            icon_path,
            os.path.join(os.path.dirname(sys.executable), icon_path) if hasattr(sys, 'frozen') else icon_path,
            os.path.join(os.path.dirname(sys.argv[0]), icon_path),
            os.path.join(os.getcwd(), icon_path),
            os.path.join(os.path.dirname(__file__), icon_path) if '__file__' in globals() else icon_path
        ]
        
        actual_icon_path = None
        for path in icon_locations:
            if os.path.exists(path):
                actual_icon_path = path
                break
        
        if hwnd != 0 and actual_icon_path:
            # Converte o caminho para o formato Windows absoluto
            icon_path_abs = os.path.abspath(actual_icon_path)
            
            # Carrega o ícone em diferentes tamanhos
            hicon_small = user32.LoadImageW(
                None,
                icon_path_abs,
                IMAGE_ICON,
                16, 16,  # Tamanho pequeno (16x16)
                LR_LOADFROMFILE
            )
            
            hicon_big = user32.LoadImageW(
                None,
                icon_path_abs,
                IMAGE_ICON,
                32, 32,  # Tamanho grande (32x32)
                LR_LOADFROMFILE
            )
            
            if hicon_small or hicon_big:
                if hicon_small:
                    # Define o ícone pequeno (barra de tarefas)
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                    try:
                        user32.SetClassLongPtrW(hwnd, GWL_HICON, hicon_small)
                    except:
                        # Fallback para sistemas 32-bit
                        user32.SetClassLongW(hwnd, GWL_HICON, hicon_small)
                
                if hicon_big:
                    # Define o ícone grande (janela)
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                
                # Força atualização da janela
                user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0004)
                
                print(f"Ícone definido com sucesso para janela: {hwnd}")
                return True
            else:
                print(f"Falha ao carregar ícone: {icon_path_abs}")
        else:
            if hwnd == 0:
                print("Janela não encontrada")
            if not actual_icon_path:
                print(f"Ícone não encontrado nos locais: {icon_locations}")
        
    except Exception as e:
        print(f"Erro ao definir ícone: {e}")
        
    return False

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

def calculate_window_positions(scale_func, min_margin_base=600):
    """
    Calculates safe window positions ensuring minimum margin from screen edges.
    The margin is also scaled by DPI to adapt to different screen configurations.
    
    Formula: window_left = screen_width - window_width - scaled_margin
    This ensures that window_left + window_width + scaled_margin = screen_width
    
    Args:
        scale_func: Function to scale UI elements based on DPI
        min_margin_base: Base margin in pixels that will be scaled (default: 600)
    
    Returns:
        tuple: (base_left_small, base_left_large, base_top)
    """
    try:
        screen_w, screen_h = pyautogui.size()
        
        # Calculate window sizes (scaled)
        small_width = scale_func(100)
        large_width = scale_func(650)
        
        # Calculate scaled margin - adapts to DPI and screen size
        scaled_margin = scale_func(min_margin_base)
        
        # Calculate positions ensuring scaled_margin free space after window's right edge
        # Formula: left_position = screen_width - window_width - scaled_margin
        base_left_small = screen_w - small_width - scaled_margin
        base_left_large = screen_w - large_width - scaled_margin
        
        # Ensure positions are not negative (in case of very small screens)
        base_left_small = max(0, base_left_small)
        base_left_large = max(0, base_left_large)
        
        # Standard top position with some margin
        base_top = 30
        
        return base_left_small, base_left_large, base_top
        
    except Exception as e:
        print(f"Could not determine screen size for window positioning: {e}")
        # Fallback values that should work on most screens
        return 1000, 400, 30

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
        opacity = 1 if e.data == "true" else 0
        
        if hasattr(self, 'page') and self.page and hasattr(self.page, 'app_instance') and hasattr(self.page.app_instance, 'animation_manager') and self.page.app_instance.animation_manager:
            # Use AnimationManager para hover async
            self.page.app_instance.animation_manager.request_play('field_hover', icon_button, duration=0.2, opacity=opacity)
        else:
            # Fallback para hover direto
            icon_button.opacity = opacity
            try:
                icon_button.update()
            except:
                pass

    def set_minimized(self, minimized: bool, animated: bool = True):
        self.is_minimized = minimized

        if animated and hasattr(self, 'page') and self.page and hasattr(self.page, 'app_instance') and hasattr(self.page.app_instance, 'animation_manager') and self.page.app_instance.animation_manager:
            # Use AnimationManager para animações async
            animation_name = 'task_minimize' if minimized else 'task_maximize'
            self.page.app_instance.animation_manager.request_play(animation_name, self, duration=0.25)
        else:
            # Fallback para animação direta
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
        # Previne o erro em caso de clique duplo, verificando se o item ainda está na lista
        if item_row in self.checklist_col.controls:
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

    @staticmethod
    def _parse_date(date_str):
        if not date_str:
            return None
        try:
            parts = date_str.split('/')
            if len(parts) != 3: return None
            day = int(parts[0]); month_name = parts[1]; year = int(parts[2])
            month_names = {v: k for k, v in TaskRow.months.items()}
            month = month_names.get(month_name)
            if not month: return None
            return datetime(year, month, day)
        except Exception:
            return None

    def _validate_dates(self):
        start_date = TaskRow._parse_date(self.start_date_field.value)
        end_date = TaskRow._parse_date(self.end_date_field.value)
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
        if self.status_field.value == "Complete":
            completion_date = datetime.now()
            completion_date_str = self._format_date(completion_date)
            self.end_date_field.value = completion_date_str

            # A task cannot be completed before its start date.
            # If the start date is in the future or invalid, set it to the completion date as well.
            current_start_date = TaskRow._parse_date(self.start_date_field.value)
            if not current_start_date or current_start_date > completion_date:
                self.start_date_field.value = completion_date_str
                try: self.start_date_field.update()
                except: pass

            try: self.end_date_field.update()
            except: pass

            if self.db_id:

                self._on_status_change() 
                self.save()
                return

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
        
        if hasattr(self, 'page') and self.page and hasattr(self.page, 'app_instance') and hasattr(self.page.app_instance, 'animation_manager') and self.page.app_instance.animation_manager:
            # Use AnimationManager para scroll async
            self.page.app_instance.animation_manager.request_play('task_scroll_to', self, duration=1.0, curve=ft.AnimationCurve.EASE_IN_OUT)
        else:
            # Fallback para scroll direto
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
        import time
        # Controle inteligente de animação baseado em detecção de batch creation
        should_animate = True
        current_time = time.time()
        
        if hasattr(self, 'page') and self.page and hasattr(self.page, 'app_instance'):
            app = self.page.app_instance
            
            # Se houve criação muito recente de task (últimos 400ms), não anima
            if hasattr(app, '_last_add_task_time'):
                time_diff = current_time - app._last_add_task_time
                if time_diff < 0.4:
                    should_animate = False
                    
            # Se há uma operação add_task em curso (busy), não anima
            if hasattr(app, '_add_task_busy') and app._add_task_busy:
                should_animate = False
        
        if should_animate and hasattr(self, 'page') and self.page and hasattr(self.page, 'app_instance') and hasattr(self.page.app_instance, 'animation_manager') and self.page.app_instance.animation_manager:
            # Usa AnimationManager para fade-in async apenas se necessário
            try:
                self.page.app_instance.animation_manager.request_play('task_fade_in', self, duration=0.2)  # Duração reduzida
            except:
                # Fallback se AnimationManager falhar
                self.opacity = 1
        else:
            # Sem animação para operações em lote - fade-in instantâneo
            self.opacity = 1
        
        if hasattr(self, 'page') and self.page:
            self.update_theme_colors()
            try:
                self.page.overlay.append(self.file_picker)
                # Só faz update se não está em modo busy (evita updates excessivos)
                if not (hasattr(self.page, 'app_instance') and hasattr(self.page.app_instance, '_add_task_busy') and self.page.app_instance._add_task_busy):
                    self.update()
                    self.page.update()
                else:
                    # Em modo busy, apenas update local sem page.update
                    self.update()
            except: pass

    def will_unmount(self):
        if hasattr(self, 'page') and self.page:
            try:
                self.page.overlay.remove(self.file_picker)
                self.page.update()
            except: pass

    def _format_date(self, date_obj):
        if not date_obj: return ""
        day = date_obj.day; month = self.months.get(date_obj.month, "Inv"); year = date_obj.year
        return f"{day:02d}/{month}/{year}"

    def _open_start_date_picker(self, e):
        end_date = TaskRow._parse_date(self.end_date_field.value)
        if end_date:
            self.start_date_picker.last_date = end_date
        else:
            # Reset if no end date is set
            self.start_date_picker.last_date = datetime(2030, 12, 31)
        if self.start_date_picker not in self.page.overlay:
            self.page.overlay.append(self.start_date_picker)
        self.page.is_picker_open = True
        self.start_date_picker.open = True
        self.page.update()

    def _open_end_date_picker(self, e):
        start_date = TaskRow._parse_date(self.start_date_field.value)
        if start_date:
            self.end_date_picker.first_date = start_date
        else:
            # Reset if no start date is set
            self.end_date_picker.first_date = datetime(2020, 1, 1)
        if self.end_date_picker not in self.page.overlay:
            self.page.overlay.append(self.end_date_picker)
        self.page.is_picker_open = True
        self.end_date_picker.open = True
        self.page.update()

    def _on_picker_dismiss(self, e):
        self.page.is_picker_open = False
        # e.control is the DatePicker that was dismissed
        if e.control in self.page.overlay:
            try:
                self.page.overlay.remove(e.control)
                self.page.update()
            except ValueError: # It might have been removed by another event
                pass

    def _on_start_date_change(self, e):
        self.page.is_picker_open = False
        selected_date = e.control.value
        self.start_date_field.value = self._format_date(selected_date)        
        if selected_date:
            self.end_date_picker.first_date = selected_date
            current_end_date = TaskRow._parse_date(self.end_date_field.value)
            if current_end_date and current_end_date < selected_date:
                self.end_date_field.value = ""
                try: self.end_date_field.update()
                except: pass

        self.start_date_field.update()
        self._on_field_change()

    def _on_end_date_change(self, e):
        self.page.is_picker_open = False
        selected_date = e.control.value
        self.end_date_field.value = self._format_date(selected_date)

        if selected_date:
            self.start_date_picker.last_date = selected_date
            current_start_date = TaskRow._parse_date(self.start_date_field.value)
            if current_start_date and current_start_date > selected_date:
                self.start_date_field.value = ""
                try: self.start_date_field.update()
                except: pass

        self.end_date_field.update()
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
        self.content = ft.Column([
            ft.Text("This action cannot be undone."), 
            ft.Text("To confirm, type the code below:"), 
            ft.Row([self.code_display_text], alignment=ft.MainAxisAlignment.CENTER), 
            self.confirmation_text, 
            self.error_text
        ], tight=True, spacing=15)
        self.actions = [ft.TextButton("Cancel", on_click=self.cancel), ft.TextButton("Delete", on_click=self.confirm)]
        self.actions_alignment = ft.MainAxisAlignment.END

    def generate_random_code(self, length=5):
        letters = string.ascii_uppercase
        self.random_code = ''.join(random.choice(letters) for _ in range(length))

    def open_dialog(self):
        self.generate_random_code()
        self.code_display_text.value = self.random_code
        self.confirmation_text.label = "Type"
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
    def __init__(self, on_auto_save_toggle, initial_value, on_close, on_dpi_change, initial_dpi_scale, on_theme_change, initial_theme, scale_func, version, on_font_size_change, initial_font_size, on_carousel_settings_change, initial_carousel_show_progress, initial_carousel_speed, on_translucency_change, initial_translucency_enabled, initial_translucency_level, on_carousel_visibility_change, initial_carousel_show_total, initial_carousel_show_ongoing, initial_carousel_show_completed, initial_carousel_show_overdue):
        super().__init__()
        self.on_auto_save_toggle = on_auto_save_toggle
        self.on_close = on_close
        self.on_dpi_change = on_dpi_change
        self.on_theme_change = on_theme_change
        self.on_font_size_change = on_font_size_change
        self.on_carousel_settings_change = on_carousel_settings_change
        self.on_carousel_visibility_change = on_carousel_visibility_change
        self.on_translucency_change = on_translucency_change
        self.scale_func = scale_func
        self.version = version
        self.modal = True # Important for dropdowns inside tabs
        self.base_font_size = initial_font_size

        # Opções de transição para o carousel
        self.carousel_transition_options = [
            ("Fade + Slide", "fade_slide"),
            ("Fade + Slide (E -> D)", "fade_slide_lr"),
            ("Slide", "slide"),
            ("Slide (Direita -> Esquerda)", "slide_rl"),
            ("Slide Push (E -> D)", "slide_push"),
            ("Slide (Esquerda -> Esquerda)", "slide_ll"),
            ("Zoom", "zoom"),
            ("Rotate", "rotate"),
            ("Bounce", "bounce"),
        ]
        # Valor inicial da transição (pode ser lido do banco/config)
        initial_transition = db.get_setting('carousel_transition', 'fade_slide')
        self.carousel_transition_dropdown = ft.Dropdown(
            label="Transição do Carousel",
            options=[ft.dropdown.Option(key=val, text=label) for label, val in self.carousel_transition_options],
            value=initial_transition,
            on_change=self._handle_carousel_setting_change,
            expand=True,
            menu_height=250
        )

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

        self.carousel_show_total_checkbox = ft.Checkbox(
            label="Total",
            value=initial_carousel_show_total,
            on_change=self._handle_carousel_visibility_change
        )
        self.carousel_show_ongoing_checkbox = ft.Checkbox(
            label="Ongoing",
            value=initial_carousel_show_ongoing,
            on_change=self._handle_carousel_visibility_change
        )
        self.carousel_show_completed_checkbox = ft.Checkbox(
            label="Completed",
            value=initial_carousel_show_completed,
            on_change=self._handle_carousel_visibility_change
        )
        self.carousel_show_overdue_checkbox = ft.Checkbox(
            label="Overdue",
            value=initial_carousel_show_overdue,
            on_change=self._handle_carousel_visibility_change
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

        # --- Tab Contents ---
        general_tab_content = ft.Column([self.auto_save_checkbox], spacing=20)

        appearance_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Display", weight=ft.FontWeight.BOLD, size=self.scale_func(14)),
                    ft.Container(
                        content=self.dpi_dropdown,
                        margin=ft.margin.only(left=10, bottom=10)
                    ),
                    ft.Divider(height=1),
                    ft.Text("Theme & Fonts", weight=ft.FontWeight.BOLD, size=self.scale_func(14)),
                    ft.Container(
                        content=ft.Column([
                            self.theme_dropdown,
                            ft.Container(height=self.scale_func(8)),  # Espaçamento responsivo
                            self.font_size_dropdown,
                        ], spacing=self.scale_func(8)),
                        margin=ft.margin.only(left=10, bottom=10)
                    ),
                ],
                spacing=self.scale_func(12),
                scroll=ft.ScrollMode.AUTO,  # Permite scroll se necessário
                expand=True
            ),
            padding=ft.padding.all(self.scale_func(10)),
            expand=True
        )

        mini_view_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Carousel", weight=ft.FontWeight.BOLD, size=self.scale_func(14)),
                    ft.Container(
                        content=ft.Column([
                            self.carousel_show_progress_checkbox,
                            ft.Container(height=self.scale_func(8)),  # Espaçamento responsivo
                            self.carousel_speed_dropdown,
                            ft.Container(height=self.scale_func(8)),
                            self.carousel_transition_dropdown,
                        ], spacing=self.scale_func(6)),
                        margin=ft.margin.only(left=10, bottom=15)
                    ),
                    ft.Text("Visible Stats:", weight=ft.FontWeight.BOLD, size=self.scale_func(12)),
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                self.carousel_show_total_checkbox,
                                self.carousel_show_ongoing_checkbox,
                            ], spacing=self.scale_func(15)),
                            ft.Container(height=self.scale_func(6)),
                            ft.Row([
                                self.carousel_show_completed_checkbox,
                                self.carousel_show_overdue_checkbox,
                            ], spacing=self.scale_func(15)),
                        ], spacing=self.scale_func(8)),
                        margin=ft.margin.only(left=10, bottom=15)
                    ),
                    ft.Divider(height=1),
                    ft.Text("Appearance", weight=ft.FontWeight.BOLD, size=self.scale_func(14)),
                    ft.Container(
                        content=ft.Column([
                            self.translucency_enabled_checkbox,
                            ft.Container(height=self.scale_func(8)),
                            ft.Container(
                                content=self.translucency_slider,
                                margin=ft.margin.only(left=20, right=20)  # Margem lateral para o slider
                            ),
                        ], spacing=self.scale_func(8)),
                        margin=ft.margin.only(left=10, bottom=10)
                    ),
                ],
                spacing=self.scale_func(12),
                scroll=ft.ScrollMode.AUTO,  # Permite scroll se necessário
                expand=True
            ),
            padding=ft.padding.all(self.scale_func(10)),
            expand=True
        )

        about_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text(f"{APP_NAME} - {VERSION}", size=self.scale_func(16), weight=ft.FontWeight.BOLD),
                    ft.Container(height=self.scale_func(8)),
                    ft.Text("A simple and effective to-do list application.", size=self.scale_func(12)),
                    ft.Divider(height=1),
                    ft.Container(height=self.scale_func(8)),
                    ft.Text(f"Data is stored locally at:", size=self.scale_func(10), weight=ft.FontWeight.BOLD),
                    ft.Container(height=self.scale_func(4)),
                    ft.Container(
                        content=ft.TextField(
                            value=APP_DATA_DIR, 
                            read_only=True, 
                            border=ft.InputBorder.UNDERLINE, 
                            text_style=ft.TextStyle(size=self.scale_func(9)),
                            min_lines=1,
                            max_lines=3,
                            expand=True
                        ),
                        margin=ft.margin.symmetric(horizontal=self.scale_func(10))
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=self.scale_func(8),
                scroll=ft.ScrollMode.AUTO,
                expand=True
            ),
            padding=ft.padding.all(self.scale_func(15)),
            expand=True
        )

        # --- Main Tabs Control ---
        self.content = ft.Container(
            content=ft.Tabs(
                [
                    ft.Tab(
                        text="General", 
                        icon=ft.Icons.TUNE, 
                        content=ft.Container(
                            content=general_tab_content, 
                            padding=ft.padding.all(self.scale_func(15)),
                            expand=True
                        )
                    ),
                    ft.Tab(
                        text="Appearance", 
                        icon=ft.Icons.PALETTE_OUTLINED, 
                        content=appearance_tab_content
                    ),
                    ft.Tab(
                        text="Mini-view", 
                        icon=ft.Icons.VIEW_COMPACT_ALT_OUTLINED, 
                        content=mini_view_tab_content
                    ),
                    ft.Tab(
                        text="About", 
                        icon=ft.Icons.INFO_OUTLINE, 
                        content=about_tab_content
                    ),
                ],
                expand=True,
                height=self.scale_func(500),  # Altura mínima responsiva
            ),
            width=self.scale_func(600),  # Largura responsiva
            height=self.scale_func(500),  # Altura responsiva
            expand=True
        )
        self.actions = [ft.TextButton("Close", on_click=self.close_dialog)]
        self.actions_alignment = ft.MainAxisAlignment.END

    def update_font_sizes(self):
        """Updates font sizes for controls inside the dialog."""
        # Atualiza tamanhos de fonte responsivos para os controles
        try:
            # Atualiza dropdown labels e outros elementos se necessário
            if hasattr(self, 'dpi_dropdown'):
                self.dpi_dropdown.text_size = self.scale_func(12)
            if hasattr(self, 'theme_dropdown'):
                self.theme_dropdown.text_size = self.scale_func(12)
            if hasattr(self, 'font_size_dropdown'):
                self.font_size_dropdown.text_size = self.scale_func(12)
            if hasattr(self, 'carousel_speed_dropdown'):
                self.carousel_speed_dropdown.text_size = self.scale_func(12)
            if hasattr(self, 'carousel_transition_dropdown'):
                self.carousel_transition_dropdown.text_size = self.scale_func(12)
                
            # Força atualização do layout
            self.update()
        except Exception:
            pass

    def _handle_dpi_change(self, e):
        self.on_dpi_change(float(e.control.value))

    def _handle_carousel_visibility_change(self, e):
        self.on_carousel_visibility_change()

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
        # Salva a opção de animação escolhida no banco/config
        if hasattr(self, 'carousel_transition_dropdown'):
            db.set_setting('carousel_transition', self.carousel_transition_dropdown.value)
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
        # Fundo sempre totalmente transparente
        super().__init__(
            width=scale_func(110),
            height=scale_func(110),
            alignment=ft.alignment.center,
            content=ft.Text("Loading...", size=scale_func(12)),
            visible=True,
            padding=scale_func(5),
            border_radius=scale_func(10),
            bgcolor=ft.Colors.TRANSPARENT
        )

    def _create_slide(self, tab_name_str, stats):
        """Creates the UI for a single slide."""
        tab_name = ft.Text(tab_name_str, weight=ft.FontWeight.BOLD, size=self.scale_func(12), text_align=ft.TextAlign.CENTER, no_wrap=True)
        
        show_progress = db.get_setting('carousel_show_progress', 'True') == 'True'
        progress_bar = ft.ProgressBar(bar_height=self.scale_func(6), expand=True, value=stats.get("progress", 0), visible=show_progress)        
        
        stats_controls = []
        if db.get_setting('carousel_show_total', 'True') == 'True':
            stats_controls.append(self._create_stat_display(ft.Icons.FUNCTIONS, ft.Colors.BLUE, "Total Tasks", stats.get("total", "0")))
        if db.get_setting('carousel_show_ongoing', 'True') == 'True':
            stats_controls.append(self._create_stat_display(ft.Icons.LOOP, ft.Colors.ORANGE, "Ongoing", stats.get("ongoing", "0")))
        if db.get_setting('carousel_show_completed', 'True') == 'True':
            stats_controls.append(self._create_stat_display(ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.GREEN, "Complete", stats.get("completed", "0")))
        if db.get_setting('carousel_show_overdue', 'True') == 'True':
            stats_controls.append(self._create_stat_display(ft.Icons.ERROR_OUTLINE, ft.Colors.RED, "Overdue", stats.get("overdue", "0")))

        return ft.Column(
            [
                tab_name,
                ft.Container(progress_bar, padding=ft.padding.symmetric(vertical=self.scale_func(1))),
                ft.Row(
                    stats_controls,
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
        """
        Start the carousel thread once the control is mounted on the page.
        Also, initialize animation properties here.
        """
        self.animate_opacity = ft.Animation(350, ft.AnimationCurve.EASE_IN_OUT)
        self.animate_offset = ft.Animation(350, ft.AnimationCurve.EASE_IN_OUT)
        self.animate_scale = ft.Animation(350, ft.AnimationCurve.EASE_IN_OUT)
        if self.rotate is None: self.rotate = ft.Rotate(angle=0)
        self.animate_rotation = ft.Animation(350, ft.AnimationCurve.EASE_IN_OUT)
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
                    # This method now runs in the background and orchestrates UI updates
                    self._perform_transition()

                speed = int(db.get_setting('carousel_speed', '5'))
                self._stop_event.wait(speed)
            except Exception as e:
                print(f"Error in MiniViewCarousel thread: {e}")
                time.sleep(5)

    def _get_next_slide_ui(self):
        """Gathers data and creates the UI for the next slide."""
        if not self.app.tabs.tabs or not len(self.app.tabs.tabs):
            return ft.Text("No Tabs", size=self.scale_func(12))

        num_tabs = len(self.app.tabs.tabs)
        if self.current_tab_index >= num_tabs:
            self.current_tab_index = 0
        
        start_index = self.current_tab_index
        agenda_tab = None
        while True:
            if self.current_tab_index >= len(self.app.tabs.tabs):
                self.current_tab_index = 0

            current_tab_control = self.app.tabs.tabs[self.current_tab_index]
            if isinstance(current_tab_control.content, AgendaTab):
                agenda_tab = current_tab_control.content
                break
            
            self.current_tab_index = (self.current_tab_index + 1) % num_tabs
            if self.current_tab_index == start_index:
                return ft.Text("No valid tabs", size=self.scale_func(12))

        stats = {
            "total": agenda_tab.overview_total_tasks.value,
            "ongoing": agenda_tab.overview_ongoing_tasks.value,
            "completed": agenda_tab.overview_completed_tasks.value,
            "overdue": agenda_tab.overview_overdue_tasks.value,
            "progress": agenda_tab.overview_completion_progress.value,
        }
        tab_name_str = agenda_tab.tab_name

        new_slide = self._create_slide(tab_name_str, stats)
        self.current_tab_index = (self.current_tab_index + 1)
        return new_slide

    def _perform_transition(self):
        """
        Runs in a background thread. Gets the next slide and orchestrates the
        animation by posting UI updates and sleeping. This replaces the old
        `do_transition` method, fixing UI blocking issues.
        """
        new_slide = self._get_next_slide_ui()

        # Try to use AnimationManager for all transitions
        if self.app and hasattr(self.app, 'animation_manager') and self.app.animation_manager:
            transition = db.get_setting('carousel_transition', 'fade_slide')
            anim_duration = 0.35
            
            # Map transition names to AnimationManager methods
            animation_map = {
                'fade_slide': 'carousel_fade_slide',
                'fade_slide_lr': 'carousel_fade_slide_lr', 
                'zoom': 'carousel_zoom',
                'rotate': 'carousel_rotate',
                'slide': 'carousel_slide',
                'slide_rl': 'carousel_slide_rl',
                'slide_push': 'carousel_slide_push',
                'slide_ll': 'carousel_slide_ll',
                'bounce': 'carousel_bounce'
            }
            
            animation_name = animation_map.get(transition, 'carousel_fade_slide')
            
            try:
                self.app.animation_manager.request_play(animation_name, self, new_content=new_slide, duration=anim_duration)
                return
            except Exception:
                pass

        # Fallback to original animation code
        def run_on_ui(action):
            if self.page:
                if hasattr(self.page, "run_threadsafe"):
                    self.page.run_threadsafe(action)
                else:
                    # Fallback for older Flet versions. This is not thread-safe.
                    action()

        def set_and_update(opacity=None, offset=None, scale=None, rotate_angle=None, content=None):
            def update_action():
                if opacity is not None: self.opacity = opacity
                if offset is not None: self.offset = offset
                if scale is not None: self.scale = scale
                if rotate_angle is not None: self.rotate.angle = rotate_angle
                if content is not None: self.content = content
                try: self.update()
                except: pass
            run_on_ui(update_action)

        transition = db.get_setting('carousel_transition', 'fade_slide')
        anim_duration = 0.35

        # Reset state before each animation
        set_and_update(opacity=1.0, offset=ft.Offset(0, 0), scale=1.0, rotate_angle=0.0)
        time.sleep(0.05) # Ensure reset is rendered

        if transition == 'zoom':
            set_and_update(scale=0.3, opacity=0.0)
            time.sleep(anim_duration)
            set_and_update(content=new_slide, scale=0.3, opacity=0.0)
            time.sleep(0.05)
            set_and_update(scale=1.0, opacity=1.0)

        elif transition == 'rotate':
            set_and_update(rotate_angle=math.pi / 2, opacity=0.0)
            time.sleep(anim_duration)
            set_and_update(content=new_slide, rotate_angle=-math.pi / 2, opacity=0.0)
            time.sleep(0.05)
            set_and_update(rotate_angle=0.0, opacity=1.0)

        elif transition == 'slide':
            set_and_update(offset=ft.Offset(-1, 0), opacity=0.0)
            time.sleep(anim_duration)
            set_and_update(content=new_slide, offset=ft.Offset(1, 0), opacity=0.0)
            set_and_update(offset=ft.Offset(0, 0), opacity=1.0)

        elif transition == 'slide_rl':
            set_and_update(offset=ft.Offset(1, 0), opacity=0.0) # Sai para a direita
            time.sleep(anim_duration)
            set_and_update(content=new_slide, offset=ft.Offset(-1, 0), opacity=0.0) 
            set_and_update(offset=ft.Offset(0, 0), opacity=1.0)

        elif transition == 'slide_push':
            set_and_update(offset=ft.Offset(1, 0), opacity=0.0) # Sai para a direita
            time.sleep(anim_duration)
            set_and_update(content=new_slide, offset=ft.Offset(-1, 0), opacity=0.0) # Entra pela esquerda
            set_and_update(offset=ft.Offset(0, 0), opacity=1.0)

        elif transition == 'slide_ll':
            set_and_update(offset=ft.Offset(-1, 0), opacity=0.0) # Sai para a esquerda
            time.sleep(anim_duration)
            set_and_update(content=new_slide, offset=ft.Offset(-1, 0), opacity=0.0) # Entra pela esquerda
            set_and_update(offset=ft.Offset(0, 0), opacity=1.0)

        elif transition == 'bounce':
            set_and_update(opacity=0.0)
            time.sleep(anim_duration)
            set_and_update(content=new_slide, offset=ft.Offset(0, 1), opacity=0.0)
            time.sleep(0.05)
            set_and_update(offset=ft.Offset(0, -0.1), opacity=1.0)
            time.sleep(anim_duration * 0.7)
            set_and_update(offset=ft.Offset(0, 0))

        elif transition == 'fade_slide_lr':
            set_and_update(opacity=0.0, offset=ft.Offset(1, 0)) # Sai para a direita
            time.sleep(anim_duration)
            set_and_update(content=new_slide, opacity=0.0, offset=ft.Offset(-1, 0)) # Imediatamente posiciona e anima a entrada
            set_and_update(opacity=1.0, offset=ft.Offset(0, 0))

        else: # Default to 'fade_slide'
            set_and_update(opacity=0.0, offset=ft.Offset(0.3, 0))
            time.sleep(anim_duration)
            set_and_update(content=new_slide, opacity=0.0, offset=ft.Offset(-0.3, 0)) # Imediatamente posiciona e anima a entrada
            set_and_update(opacity=1.0, offset=ft.Offset(0, 0))

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

        self.selected_status_for_chart = "ongoing"
        self.total_card = self._create_stat_card("Total Tasks", self.overview_total_tasks, ft.Icons.FUNCTIONS, ft.Colors.BLUE, lambda e: self._on_status_card_click("total"))
        self.ongoing_card = self._create_stat_card("Ongoing", self.overview_ongoing_tasks, ft.Icons.LOOP, ft.Colors.ORANGE, lambda e: self._on_status_card_click("ongoing"))
        self.completed_card = self._create_stat_card("Completed", self.overview_completed_tasks, ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.GREEN, lambda e: self._on_status_card_click("completed"))
        self.overdue_card = self._create_stat_card("Overdue", self.overview_overdue_tasks, ft.Icons.ERROR_OUTLINE, ft.Colors.RED, lambda e: self._on_status_card_click("overdue"))
        
        self.chart_year_selector = ft.Dropdown(
            on_change=self._update_chart,
            width=self.scale_func(120),
            text_style=ft.TextStyle(size=self.scale_func(self.base_font_size)),
            content_padding=ft.padding.symmetric(vertical=self.scale_func(5), horizontal=self.scale_func(10)),
            options=[ft.dropdown.Option(str(y)) for y in range(2025, 2041)],
            value=str(datetime.now().year) if 2025 <= datetime.now().year <= 2040 else "2025"
        )
        self.tasks_chart = ft.LineChart(
            tooltip_bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLUE_GREY),
            expand=True, height=self.scale_func(200), data_series=[],
            border=ft.border.all(1, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
            horizontal_grid_lines=ft.ChartGridLines(interval=5, color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE), width=1),
            vertical_grid_lines=ft.ChartGridLines(interval=1, color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE), width=1),
            left_axis=ft.ChartAxis(labels_size=self.scale_func(10)),
            bottom_axis=ft.ChartAxis(
                labels=[ft.ChartAxisLabel(value=i, label=ft.Text(TaskRow.months[i+1], size=self.scale_func(10))) for i in range(12)],
                labels_size=self.scale_func(30),
            ),
            min_y=0, min_x=0, max_x=11,
        )
        
        self.overview_content = ft.Container(
            ft.Column([
                ft.Row([
                    self.total_card, self.ongoing_card, self.completed_card, self.overdue_card
                ], spacing=self.scale_func(15), alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                ft.Divider(height=self.scale_func(30)),
                ft.Text("Completion Progress", style=ft.TextThemeStyle.TITLE_MEDIUM),
                ft.Container(
                    content=ft.Row([self.overview_completion_progress, self.overview_completion_percent], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=self.scale_func(10)),
                    padding=ft.padding.only(top=self.scale_func(10))
                ),
                ft.Divider(height=self.scale_func(30)),
                ft.Row(
                    [ft.Text("Activity Chart", style=ft.TextThemeStyle.TITLE_MEDIUM), ft.Container(expand=True), self.chart_year_selector],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                self.tasks_chart,
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

    def _create_stat_card(self, title: str, value_control: ft.Control, icon: str, icon_color: str, on_click):
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
            ink=True, on_click=on_click
        )

    def _on_status_card_click(self, status):
        self.selected_status_for_chart = status
        self._update_chart()

    def did_mount(self):
        self.update_theme_colors()
        self.selected_status_for_chart = "ongoing"
        self._update_chart()

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

    def _populate_chart_selectors(self):
        # Agora fixa os anos de 2025 a 2040
        self.chart_year_selector.options = [ft.dropdown.Option(str(y)) for y in range(2025, 2041)]
        current_year = datetime.now().year
        if 2025 <= current_year <= 2040:
            self.chart_year_selector.value = str(current_year)
        else:
            self.chart_year_selector.value = "2025"
        try:
            self.chart_year_selector.update()
        except:
            pass

    def _update_chart(self, e=None):
        if not hasattr(self, 'page') or not self.page or not self.chart_year_selector.value:
            self.tasks_chart.data_series = []
            try: self.tasks_chart.update()
            except: pass
            return

        selected_year = int(self.chart_year_selector.value)
        all_tasks = self.ongoing_list.controls + self.complete_list.controls
        now = datetime.now()
        counts = {i: 0 for i in range(12)}

        for task in all_tasks:
            if not isinstance(task, TaskRow): continue
            start_date = TaskRow._parse_date(task.start_date_field.value)
            end_date = TaskRow._parse_date(task.end_date_field.value)
            status = (task.status_field.value or '').lower()

            if self.selected_status_for_chart == "total":
                # Conta todas as tarefas criadas no mês
                if start_date and start_date.year == selected_year:
                    counts[start_date.month - 1] += 1
            elif self.selected_status_for_chart == "ongoing":
                if status == "ongoing" and start_date and start_date.year == selected_year:
                    counts[start_date.month - 1] += 1
            elif self.selected_status_for_chart == "completed":
                if status == "complete" and end_date and end_date.year == selected_year:
                    counts[end_date.month - 1] += 1
            elif self.selected_status_for_chart == "overdue":
                if status != "complete" and end_date and end_date.year == selected_year and end_date.replace(hour=23, minute=59) < now:
                    counts[end_date.month - 1] += 1

        max_y = max(counts.values()) if all_tasks else 0
        top_y = 5 if max_y < 5 else (math.ceil(max_y / 5)) * 5
        self.tasks_chart.max_y = top_y
        self.tasks_chart.horizontal_grid_lines.interval = max(1, top_y / 5)
        self.tasks_chart.left_axis.labels = [ft.ChartAxisLabel(value=i, label=ft.Text(str(i), size=self.scale_func(10))) for i in range(0, top_y + 1, max(1, top_y // 5))]
        color_map = {
            "total": ft.Colors.BLUE,
            "ongoing": ft.Colors.ORANGE,
            "completed": ft.Colors.GREEN,
            "overdue": ft.Colors.RED
        }
        color = color_map.get(self.selected_status_for_chart, ft.Colors.BLUE)
        self.tasks_chart.data_series = [
            ft.LineChartData(
                color=color,
                stroke_width=3,
                curved=True,
                stroke_cap_round=True,
                below_line_bgcolor=ft.Colors.with_opacity(0.2, color),
                data_points=[ft.LineChartDataPoint(x=m, y=c) for m, c in counts.items()]
            )
        ]
        try: self.tasks_chart.update()
        except: pass

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
            new_angle = self.reorder_mode_btn.rotate.angle + math.pi * 2
        else:
            self.reorder_mode_btn.icon = ft.Icons.SWAP_VERT
            self.reorder_mode_btn.tooltip = "Enable reordering"
            self.reorder_mode_btn.icon_color = None
            new_angle = self.reorder_mode_btn.rotate.angle - math.pi * 2

        # Use AnimationManager for button rotation
        if hasattr(self, 'page') and self.page and hasattr(self.page, 'app_instance') and hasattr(self.page.app_instance, 'animation_manager') and self.page.app_instance.animation_manager:
            self.page.app_instance.animation_manager.request_play('button_rotate', self.reorder_mode_btn, duration=0.4, angle=new_angle)
        else:
            # Fallback para rotação direta
            self.reorder_mode_btn.rotate.angle = new_angle

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
        self._populate_chart_selectors()
        self._update_chart()
        try: self.update()
        except: pass

    def add_task(self, e=None, data=None):
        import time
        import threading
        
        # Proteção contra execuções simultâneas
        if not hasattr(self, '_add_task_busy'):
            self._add_task_busy = False
            
        if self._add_task_busy:
            return None
            
        # Throttling mais rigoroso: previne múltiplos cliques rápidos
        current_time = time.time()
        if hasattr(self, '_last_add_task_time'):
            time_diff = current_time - self._last_add_task_time
            if time_diff < 0.5:  # Aumentado de 300ms para 500ms
                return None
                
        # Cancela debounce anterior se existir
        if hasattr(self, '_add_task_debounce_timer'):
            if self._add_task_debounce_timer and self._add_task_debounce_timer.is_alive():
                return None  # Ignora cliques durante debounce
        
        # Marca como busy
        self._add_task_busy = True
        self._last_add_task_time = current_time
        
        try:
            # Cria task com controle mais restrito
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
            self._populate_chart_selectors()
            self._update_chart()
            
            # Auto-save apenas se não for duplicação
            if (self.get_auto_save_setting and self.get_auto_save_setting()) and not data:
                row.save()
            
            # Debounce para page.update com cancelamento de timer anterior
            def debounced_update():
                time.sleep(0.2)  # 200ms debounce
                try:
                    self.page.update()
                except:
                    pass
                finally:
                    self._add_task_busy = False  # Libera busy flag após update
                    
            # Cancela timer anterior e cria novo
            if hasattr(self, '_add_task_debounce_timer') and self._add_task_debounce_timer and self._add_task_debounce_timer.is_alive():
                # Timer anterior ainda rodando, será cancelado automaticamente
                pass
                
            self._add_task_debounce_timer = threading.Timer(0.2, debounced_update)
            self._add_task_debounce_timer.start()
            
            return row
            
        except Exception as ex:
            self._add_task_busy = False  # Libera busy em caso de erro
            return None

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
            self._update_chart()
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
        import time
        
        # Throttling para duplicação: previne múltiplos cliques rápidos
        current_time = time.time()
        if hasattr(self, '_last_duplicate_time'):
            time_diff = current_time - self._last_duplicate_time
            if time_diff < 0.3:  # 300ms mínimo entre duplicações
                return
                
        self._last_duplicate_time = current_time
        
        data = original_task_row.get_data()
        data['title'] = f"{data.get('title', '')} (Copy)"

        # Create a new task row instance by reusing add_task
        new_row = self.add_task(data=data)
        
        # Verifica se add_task foi bem-sucedido (não foi throttled)
        if not new_row:
            return

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
        self._populate_chart_selectors()
        self._update_chart()

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
        self._populate_chart_selectors()
        self._update_chart()
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
        self._populate_chart_selectors()
        self._update_chart()
        
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
        self.carousel_show_total = db.get_setting('carousel_show_total', 'True') == 'True'
        self.carousel_show_ongoing = db.get_setting('carousel_show_ongoing', 'True') == 'True'
        self.carousel_show_completed = db.get_setting('carousel_show_completed', 'True') == 'True'
        self.carousel_show_overdue = db.get_setting('carousel_show_overdue', 'True') == 'True'
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
            initial_translucency_level=self.translucency_level,
            on_carousel_visibility_change=self.change_carousel_visibility_settings,
            initial_carousel_show_total=self.carousel_show_total,
            initial_carousel_show_ongoing=self.carousel_show_ongoing,
            initial_carousel_show_completed=self.carousel_show_completed,
            initial_carousel_show_overdue=self.carousel_show_overdue
        )
        self.delete_dialog = DeleteConfirmationDialog(on_confirm=self.delete_tab, on_cancel=self.close_delete_dialog, scale_func=self.scale_func)
        self.add_tab_btn = ft.ElevatedButton(text="New Tab", icon=ft.Icons.ADD, on_click=self.add_new_tab)
        
        self.settings_btn = ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="Settings", on_click=self.open_settings_dialog)
        self.pin_switch = ft.Switch(value=False, on_change=self.toggle_pin, tooltip="Pin window open")
        self.header = ft.Row([
            ft.Text(f"{APP_NAME}", style=ft.TextThemeStyle.HEADLINE_SMALL),
            ft.Container(expand=True), 
            self.settings_btn, 
            self.pin_switch, self.add_tab_btn
        ])
        
        self.controls = [self.header, self.tabs]
        self.apply_theme(self.theme_name)
        # Central animation manager used across the app
        try:
            self.animation_manager = AnimationManager(self.page)
        except Exception:
            self.animation_manager = None

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

    def apply_translucency(self, update_page=True):
        is_mini_view = self.page.app_container.opacity == 0

        if is_mini_view and self.translucency_enabled:
            self.page.window.bgcolor = ft.Colors.TRANSPARENT
            self.page.window.opacity = self.translucency_level / 100.0
        else:
            # Full view, or mini-view without translucency, should be opaque
            self.page.window.bgcolor = None # Let Flet use the theme's background
            self.page.window.opacity = 1.0
        
        if update_page:
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

    def change_carousel_visibility_settings(self):
        show_total = self.settings_dialog.carousel_show_total_checkbox.value
        show_ongoing = self.settings_dialog.carousel_show_ongoing_checkbox.value
        show_completed = self.settings_dialog.carousel_show_completed_checkbox.value
        show_overdue = self.settings_dialog.carousel_show_overdue_checkbox.value

        db.set_setting('carousel_show_total', str(show_total))
        db.set_setting('carousel_show_ongoing', str(show_ongoing))
        db.set_setting('carousel_show_completed', str(show_completed))
        db.set_setting('carousel_show_overdue', str(show_overdue))

        self.carousel_show_total = show_total
        self.carousel_show_ongoing = show_ongoing
        self.carousel_show_completed = show_completed
        self.carousel_show_overdue = show_overdue

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
                    if isinstance(task_row, TaskRow):
                        task_row.update_theme_colors()
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
                    if not (end_date_str and (end_date := TaskRow._parse_date(end_date_str))):
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
        # Evita duplicar tab no DB se já existe (proteção extra)
        existing_tabs = db.list_tabs()
        if tab_name not in existing_tabs:
            db.add_tab(tab_name)
            
        tab_content = AgendaTab(tab_name, self.open_delete_dialog_request, self.page, self.delete_dialog, self.get_auto_save_setting, self.scale_func, self.base_font_size)
        editable_label = EditableTabLabel(tab_name, self.rename_tab, self.scale_func, self.base_font_size)
        tab = ft.Tab(content=tab_content, tab_content=editable_label)
        self.tabs.tabs.append(tab)
        
        try:
            # Carrega tasks de forma mais controlada
            tab_content.load_tasks()
            
            # Só faz update se não está em modo busy (evita updates excessivos durante operações em lote)
            if not (hasattr(self, '_add_new_tab_busy') and self._add_new_tab_busy):
                self.tabs.update()
        except Exception:
            pass

    def add_new_tab(self, e=None):
        import time
        import threading
        
        # Proteção contra execuções simultâneas
        if not hasattr(self, '_add_new_tab_busy'):
            self._add_new_tab_busy = False
            
        if self._add_new_tab_busy:
            return None
            
        # Throttling rigoroso: previne múltiplos cliques rápidos
        current_time = time.time()
        if hasattr(self, '_last_add_new_tab_time'):
            time_diff = current_time - self._last_add_new_tab_time
            if time_diff < 0.5:  # 500ms mínimo entre criações de tab
                return None
                
        # Cancela debounce anterior se existir
        if hasattr(self, '_add_new_tab_debounce_timer'):
            if self._add_new_tab_debounce_timer and self._add_new_tab_debounce_timer.is_alive():
                return None  # Ignora cliques durante debounce
        
        # Marca como busy
        self._add_new_tab_busy = True
        self._last_add_new_tab_time = current_time
        
        try:
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
            
            # Debounce para tabs.update() com cancelamento de timer anterior
            def debounced_update():
                time.sleep(0.2)  # 200ms debounce
                try:
                    self.tabs.update()
                except:
                    pass
                finally:
                    self._add_new_tab_busy = False  # Libera busy flag após update
                    
            # Cancela timer anterior e cria novo
            if hasattr(self, '_add_new_tab_debounce_timer') and self._add_new_tab_debounce_timer and self._add_new_tab_debounce_timer.is_alive():
                # Timer anterior ainda rodando, será cancelado automaticamente
                pass
                
            self._add_new_tab_debounce_timer = threading.Timer(0.2, debounced_update)
            self._add_new_tab_debounce_timer.start()
            
        except Exception as ex:
            self._add_new_tab_busy = False  # Libera busy em caso de erro

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


# --- Animation Manager -------------------------------------------------



class AnimationManager:
    """Central async animation manager.

    Runs an asyncio event loop in a background thread so animations use
    non-blocking `asyncio.sleep`. UI updates are dispatched to the Flet
    `page` using `page.run_threadsafe` to ensure thread-safety.
    """

    def __init__(self, page):
        self.page = page
        self.loop = asyncio.new_event_loop()
        self._active_animations = 0
        self._max_concurrent_animations = 10  # Limite de animações simultâneas
        self._registry = {
            'drop_bounce_out': self._drop_bounce_out,
            'window_expand': self._window_expand,
            'window_shrink': self._window_shrink,
            # Task animations
            'task_minimize': self._task_minimize,
            'task_maximize': self._task_maximize,
            'task_fade_in': self._task_fade_in,
            'task_scroll_to': self._task_scroll_to,
            'field_hover': self._field_hover,
            'button_rotate': self._button_rotate,
            # Carousel transitions
            'carousel_fade_slide': self._carousel_fade_slide,
            'carousel_fade_slide_lr': self._carousel_fade_slide_lr,
            'carousel_zoom': self._carousel_zoom,
            'carousel_rotate': self._carousel_rotate,
            'carousel_slide': self._carousel_slide,
            'carousel_slide_rl': self._carousel_slide_rl,
            'carousel_slide_push': self._carousel_slide_push,
            'carousel_slide_ll': self._carousel_slide_ll,
            'carousel_bounce': self._carousel_bounce,
        }
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._thread.join(timeout=1.0)
        except Exception:
            pass

    def request_play(self, name, target_control, new_content=None, duration=1.0, **kwargs):
        """Schedule a named animation on the manager's loop.

        This is thread-safe and can be called from background threads.
        """
        # Verifica limite de animações simultâneas
        if self._active_animations >= self._max_concurrent_animations:
            # Se está no limite, executa swap instantâneo sem animação
            def _instant_swap():
                try:
                    if new_content is not None:
                        target_control.content = new_content
                    # Para animações de task, define valores finais
                    if name == 'task_fade_in':
                        target_control.opacity = 1
                    elif name in ['task_minimize', 'task_maximize']:
                        is_minimized = name == 'task_minimize'
                        if hasattr(target_control, 'expandable_content'):
                            target_control.expandable_content.height = 0 if is_minimized else None
                            target_control.expandable_content.opacity = 0 if is_minimized else 1
                        if hasattr(target_control, 'minimized_info'):
                            target_control.minimized_info.visible = is_minimized
                    target_control.update()
                except Exception:
                    pass
            
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(_instant_swap)
                else:
                    _instant_swap()
            except Exception:
                pass
            return None
        
        coro_factory = self._registry.get(name)
        if not coro_factory:
            # unknown animation: perform an instant swap on UI thread
            def _swap():
                try:
                    if new_content is not None:
                        target_control.content = new_content
                        target_control.update()
                except Exception:
                    pass
            
            # Use safe update method
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(_swap)
                else:
                    _swap()
            except Exception:
                pass
            return None

        # Wrapper que incrementa/decrementa contador de animações
        async def animation_wrapper():
            self._active_animations += 1
            try:
                await coro_factory(target_control, new_content, duration, **kwargs)
            finally:
                self._active_animations -= 1

        coro = animation_wrapper()
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future

    async def _drop_bounce_out(self, target, new_content, duration=1.0, **kwargs):
        """Drop from above, bounce 3x, stabilize, then exit down.

        All UI mutations are dispatched via safe update method.
        """
        total = max(0.6, float(duration))
        fall_time = total * 0.35
        bounce_time = total * 0.45
        exit_time = total * 0.20

        def _set_props(opacity=None, offset=None, scale=None, rotate=None):
            try:
                if opacity is not None:
                    target.opacity = opacity
                if offset is not None:
                    target.offset = offset
                if scale is not None:
                    target.scale = scale
                if rotate is not None:
                    target.rotate = rotate
                target.update()
            except Exception:
                pass

        # Use fallback method for UI updates (compatible with older Flet)
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    # Fallback: call directly (may not be thread-safe but works)
                    func()
            except Exception:
                pass

        # Start above the view, invisible
        _safe_update(lambda: _set_props(opacity=0.0, offset=ft.Offset(0, -1.5)))
        await asyncio.sleep(0.02)

        # Falling in (becomes visible while falling)
        steps = 6
        for i in range(steps):
            t = (i + 1) / steps
            y = -1.5 + (t ** 1.8) * 1.8
            op = min(1.0, t * 1.4)
            _safe_update(lambda y=y, op=op: _set_props(opacity=op, offset=ft.Offset(0, y)))
            await asyncio.sleep(fall_time / steps)

        # Bounce sequence (3 decreasing bounces)
        bounces = [0.35, -0.18, 0.08]
        for amp in bounces:
            steps = 5
            for i in range(steps):
                t = (i + 1) / steps
                y = amp * (1 - (t - 1) ** 2)
                _safe_update(lambda y=y: _set_props(offset=ft.Offset(0, y)))
                await asyncio.sleep(bounce_time / (len(bounces) * steps))

        # Stabilize at center
        _safe_update(lambda: _set_props(offset=ft.Offset(0, 0), opacity=1.0))
        await asyncio.sleep(0.06)

        # Exit downwards
        steps = 6
        for i in range(steps):
            t = (i + 1) / steps
            y = t * 2.0
            op = max(0.0, 1.0 - t * 1.2)
            _safe_update(lambda y=y, op=op: _set_props(offset=ft.Offset(0, y), opacity=op))
            await asyncio.sleep(exit_time / steps)

        # Final swap of content on UI thread
        def _swap():
            try:
                if new_content is not None:
                    target.content = new_content
                target.offset = ft.Offset(0, 0)
                target.opacity = 1.0
                target.scale = 1.0
                target.rotate = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_swap)

    async def _window_expand(self, target, new_content=None, duration=1.0, **kwargs):
        """Anima a expansão da janela usando propriedades nativas do Flet.
        
        Mantém a posição fixa e anima apenas width/height de forma suave.
        """
        scale_func = kwargs.get('scale_func', lambda x: x)

        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Configurar a animação nativa
        def _animate_expand():
            try:
                # Tamanhos finais
                final_width = scale_func(650)
                final_height = scale_func(900)
                
                # Manter posição atual
                current_left = self.page.window.left
                current_top = self.page.window.top
                
                # Preparar conteúdo
                self.page.app_container.opacity = 1
                self.page.mini_icon.visible = False
                
                # Definir tamanhos finais (Flet vai animar automaticamente)
                self.page.window.left = current_left
                self.page.window.top = current_top  
                self.page.window.width = final_width
                self.page.window.height = final_height
                
                # Configurações finais
                self.page.window.bgcolor = None
                self.page.window.opacity = 1.0
                
                self.page.update()
                
            except Exception:
                pass
        
        _safe_update(_animate_expand)
        
        # Aguardar a duração da animação
        await asyncio.sleep(duration)

    async def _window_shrink(self, target, new_content=None, duration=1.0, **kwargs):
        """Anima a redução da janela usando propriedades nativas do Flet.
        
        Mantém a posição e anima apenas width/height de forma suave.
        """
        base_left_small = kwargs.get('base_left_small', 1000)
        scale_func = kwargs.get('scale_func', lambda x: x)
        app_instance = kwargs.get('app_instance')
        
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Fechar dialog de configurações se estiver aberto
        def _close_settings_and_animate():
            try:
                if app_instance and hasattr(app_instance, 'settings_dialog') and app_instance.settings_dialog.open:
                    app_instance.settings_dialog.open = False

                # Tamanhos finais (mini)
                final_width = scale_func(100)
                final_height = scale_func(100)
                
                # Preparar conteúdo
                self.page.app_container.opacity = 0
                self.page.mini_icon.visible = True
                
                # Definir tamanhos finais e posição (Flet anima automaticamente)
                self.page.window.left = base_left_small
                self.page.window.width = final_width
                self.page.window.height = final_height
                
                # Aplicar translucência
                if app_instance:
                    app_instance.apply_translucency(update_page=False)
                    final_opacity = (app_instance.translucency_level / 100.0 
                                   if app_instance.translucency_enabled else 1.0)
                    self.page.window.opacity = final_opacity
                else:
                    self.page.window.opacity = 1.0
                
                self.page.update()
                
            except Exception:
                pass
        
        _safe_update(_close_settings_and_animate)
        
        # Aguardar a duração da animação
        await asyncio.sleep(duration)

    # --- Task Animation Methods ---

    async def _task_minimize(self, target, new_content=None, duration=0.25, **kwargs):
        """Anima a minimização de uma tarefa com altura e opacidade."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        def _animate():
            try:
                if hasattr(target, 'expandable_content'):
                    target.expandable_content.animate_size = ft.Animation(duration=int(duration * 1000), curve=ft.AnimationCurve.DECELERATE)
                    target.expandable_content.height = 0
                    target.expandable_content.opacity = 0
                    if hasattr(target, 'minimized_info'):
                        target.minimized_info.visible = True
                    if hasattr(target, 'minimize_btn') and hasattr(target.minimize_btn, 'rotate'):
                        target.minimize_btn.rotate.angle = math.pi
                        target.minimize_btn.tooltip = "Maximize"
                    target.update()
            except Exception:
                pass

        _safe_update(_animate)
        await asyncio.sleep(duration)

        # Remove animation after completion
        def _cleanup():
            try:
                if hasattr(target, 'expandable_content'):
                    target.expandable_content.animate_size = None
                    target.update()
            except Exception:
                pass
        
        _safe_update(_cleanup)

    async def _task_maximize(self, target, new_content=None, duration=0.25, **kwargs):
        """Anima a maximização de uma tarefa com altura e opacidade."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        def _animate():
            try:
                if hasattr(target, 'expandable_content'):
                    target.expandable_content.animate_size = ft.Animation(duration=int(duration * 1000), curve=ft.AnimationCurve.DECELERATE)
                    target.expandable_content.height = None
                    target.expandable_content.opacity = 1
                    if hasattr(target, 'minimized_info'):
                        target.minimized_info.visible = False
                    if hasattr(target, 'minimize_btn') and hasattr(target.minimize_btn, 'rotate'):
                        target.minimize_btn.rotate.angle = 0
                        target.minimize_btn.tooltip = "Minimize"
                    target.update()
            except Exception:
                pass

        _safe_update(_animate)
        await asyncio.sleep(duration)

        # Remove animation after completion
        def _cleanup():
            try:
                if hasattr(target, 'expandable_content'):
                    target.expandable_content.animate_size = None
                    target.update()
            except Exception:
                pass
        
        _safe_update(_cleanup)

    async def _task_fade_in(self, target, new_content=None, duration=0.3, **kwargs):
        """Anima o fade-in de uma tarefa de forma otimizada."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        def _start_fade():
            try:
                target.opacity = 0
                target.update()
            except Exception:
                pass

        def _finish_fade():
            try:
                target.opacity = 1
                target.update()
            except Exception:
                pass

        # Animação mais rápida e eficiente para fade-in
        _safe_update(_start_fade)
        await asyncio.sleep(0.01)  # Reduzido de 0.02 para 0.01
        _safe_update(_finish_fade)
        await asyncio.sleep(duration * 0.5)  # Reduzir tempo de espera total

    async def _task_scroll_to(self, target, new_content=None, duration=1.0, **kwargs):
        """Anima o scroll para uma tarefa específica."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        def _scroll():
            try:
                curve = kwargs.get('curve', ft.AnimationCurve.EASE_IN_OUT)
                target.scroll_to(duration=int(duration * 1000), curve=curve)
            except Exception:
                pass

        _safe_update(_scroll)
        await asyncio.sleep(duration)

    async def _field_hover(self, target, new_content=None, duration=0.2, **kwargs):
        """Anima o hover de campos com opacidade."""
        opacity = kwargs.get('opacity', 1.0)
        
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        def _animate():
            try:
                target.opacity = opacity
                target.update()
            except Exception:
                pass

        _safe_update(_animate)
        await asyncio.sleep(duration)

    async def _button_rotate(self, target, new_content=None, duration=0.4, **kwargs):
        """Anima a rotação de botões."""
        angle = kwargs.get('angle', math.pi)
        
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        def _animate():
            try:
                if hasattr(target, 'rotate'):
                    target.rotate.angle = angle
                target.update()
            except Exception:
                pass

        _safe_update(_animate)
        await asyncio.sleep(duration)

    # --- Carousel Animation Methods ---

    async def _carousel_fade_slide(self, target, new_content, duration=0.35, **kwargs):
        """Animação fade + slide padrão do carousel."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Exit animation
        def _exit():
            try:
                target.opacity = 0.0
                target.offset = ft.Offset(0.3, 0)
                target.update()
            except Exception:
                pass

        _safe_update(_exit)
        await asyncio.sleep(duration)

        # Swap content and enter animation
        def _enter():
            try:
                target.content = new_content
                target.offset = ft.Offset(-0.3, 0)
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_enter)
        await asyncio.sleep(0.05)

        # Final position
        def _final():
            try:
                target.opacity = 1.0
                target.offset = ft.Offset(0, 0)
                target.update()
            except Exception:
                pass

        _safe_update(_final)

    async def _carousel_fade_slide_lr(self, target, new_content, duration=0.35, **kwargs):
        """Animação fade + slide da esquerda para direita."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Exit to right
        def _exit():
            try:
                target.opacity = 0.0
                target.offset = ft.Offset(1, 0)
                target.update()
            except Exception:
                pass

        _safe_update(_exit)
        await asyncio.sleep(duration)

        # Enter from left
        def _enter():
            try:
                target.content = new_content
                target.opacity = 0.0
                target.offset = ft.Offset(-1, 0)
                target.update()
            except Exception:
                pass

        _safe_update(_enter)
        await asyncio.sleep(0.05)

        def _final():
            try:
                target.opacity = 1.0
                target.offset = ft.Offset(0, 0)
                target.update()
            except Exception:
                pass

        _safe_update(_final)

    async def _carousel_zoom(self, target, new_content, duration=0.35, **kwargs):
        """Animação de zoom do carousel."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Zoom out
        def _zoom_out():
            try:
                target.scale = 0.3
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_zoom_out)
        await asyncio.sleep(duration)

        # Swap content
        def _swap():
            try:
                target.content = new_content
                target.scale = 0.3
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_swap)
        await asyncio.sleep(0.05)

        # Zoom in
        def _zoom_in():
            try:
                target.scale = 1.0
                target.opacity = 1.0
                target.update()
            except Exception:
                pass

        _safe_update(_zoom_in)

    async def _carousel_rotate(self, target, new_content, duration=0.35, **kwargs):
        """Animação de rotação do carousel."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Rotate out
        def _rotate_out():
            try:
                target.rotate.angle = math.pi / 2
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_rotate_out)
        await asyncio.sleep(duration)

        # Swap content
        def _swap():
            try:
                target.content = new_content
                target.rotate.angle = -math.pi / 2
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_swap)
        await asyncio.sleep(0.05)

        # Rotate in
        def _rotate_in():
            try:
                target.rotate.angle = 0.0
                target.opacity = 1.0
                target.update()
            except Exception:
                pass

        _safe_update(_rotate_in)

    async def _carousel_slide(self, target, new_content, duration=0.35, **kwargs):
        """Animação de slide básico do carousel."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Slide out left
        def _slide_out():
            try:
                target.offset = ft.Offset(-1, 0)
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_slide_out)
        await asyncio.sleep(duration)

        # Swap and slide in from right
        def _slide_in():
            try:
                target.content = new_content
                target.offset = ft.Offset(1, 0)
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_slide_in)
        await asyncio.sleep(0.05)

        def _final():
            try:
                target.offset = ft.Offset(0, 0)
                target.opacity = 1.0
                target.update()
            except Exception:
                pass

        _safe_update(_final)

    async def _carousel_slide_rl(self, target, new_content, duration=0.35, **kwargs):
        """Animação de slide da direita para esquerda."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Slide out right
        def _slide_out():
            try:
                target.offset = ft.Offset(1, 0)
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_slide_out)
        await asyncio.sleep(duration)

        # Slide in from left
        def _slide_in():
            try:
                target.content = new_content
                target.offset = ft.Offset(-1, 0)
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_slide_in)
        await asyncio.sleep(0.05)

        def _final():
            try:
                target.offset = ft.Offset(0, 0)
                target.opacity = 1.0
                target.update()
            except Exception:
                pass

        _safe_update(_final)

    async def _carousel_slide_push(self, target, new_content, duration=0.35, **kwargs):
        """Animação de push slide."""
        await self._carousel_slide_rl(target, new_content, duration, **kwargs)

    async def _carousel_slide_ll(self, target, new_content, duration=0.35, **kwargs):
        """Animação de slide duplo à esquerda."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Slide out left
        def _slide_out():
            try:
                target.offset = ft.Offset(-1, 0)
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_slide_out)
        await asyncio.sleep(duration)

        # Slide in from left
        def _slide_in():
            try:
                target.content = new_content
                target.offset = ft.Offset(-1, 0)
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_slide_in)
        await asyncio.sleep(0.05)

        def _final():
            try:
                target.offset = ft.Offset(0, 0)
                target.opacity = 1.0
                target.update()
            except Exception:
                pass

        _safe_update(_final)

    async def _carousel_bounce(self, target, new_content, duration=0.35, **kwargs):
        """Animação de bounce do carousel."""
        def _safe_update(func):
            try:
                if hasattr(self.page, 'run_threadsafe'):
                    self.page.run_threadsafe(func)
                else:
                    func()
            except Exception:
                pass

        # Fade out
        def _fade_out():
            try:
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_fade_out)
        await asyncio.sleep(duration)

        # Swap content and start bounce
        def _bounce_start():
            try:
                target.content = new_content
                target.offset = ft.Offset(0, 1)
                target.opacity = 0.0
                target.update()
            except Exception:
                pass

        _safe_update(_bounce_start)
        await asyncio.sleep(0.05)

        # Bounce up
        def _bounce_up():
            try:
                target.offset = ft.Offset(0, -0.1)
                target.opacity = 1.0
                target.update()
            except Exception:
                pass

        _safe_update(_bounce_up)
        await asyncio.sleep(duration * 0.7)

        # Settle
        def _settle():
            try:
                target.offset = ft.Offset(0, 0)
                target.update()
            except Exception:
                pass

        _safe_update(_settle)


def main(page: ft.Page):
    page.title = "Todo APP"
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.window.resizable = False
    page.window.always_on_top = True

    db.init_db()
    app = AgendaApp(page)
    page.app_instance = app

    scale_func = app.scale_func
    page.window.width = scale_func(100)
    page.window.height = scale_func(100)

    # --- Posição base da janela ---
    base_left_small, base_left_large, base_top = calculate_window_positions(scale_func)

    page.window.left = base_left_small
    page.window.top = base_top
    
    # Habilitar animações nativas na janela
    page.window.animate_size = ft.Animation(duration=500, curve=ft.AnimationCurve.EASE_OUT)
    page.window.animate_position = ft.Animation(duration=500, curve=ft.AnimationCurve.EASE_OUT)

    # --- Containers principais ---
    page.app_container = ft.Container(
        content=app,
        expand=True,
        opacity=0,
        animate_opacity=10,   # fade rápido
        padding=scale_func(15)
    )
    page.mini_icon = MiniViewCarousel(app, scale_func)
    page.mini_icon.visible = False  # começa invisível

    stack = ft.Stack(expand=True, controls=[page.app_container, page.mini_icon])
    page.add(stack)

    app.load_tabs()
    app.check_all_due_dates()
    app.apply_translucency()

    page.pinned = False
    page.is_animating = False
    page.is_picker_open = False # Track if a date picker is open
    page.is_file_picker_open = False # Track if a file picker is open

    # --- Expandir ---
    def expand():
        if page.is_animating:
            return

        page.is_animating = True
        
        # Use AnimationManager if available
        if hasattr(app, 'animation_manager') and app.animation_manager:
            def _on_complete():
                page.is_animating = False
            
            try:
                future = app.animation_manager.request_play(
                    'window_expand',
                    target_control=None,  # Not used for window animations
                    duration=0.3,
                    base_left_large=base_left_large,
                    scale_func=scale_func
                )
                # Schedule completion callback
                if future:
                    def _wait_complete():
                        try:
                            future.result(timeout=2.0)
                        except Exception:
                            pass
                        finally:
                            _on_complete()
                    threading.Thread(target=_wait_complete, daemon=True).start()
                else:
                    _on_complete()
            except Exception:
                # Fallback to original animation
                _expand_fallback()
        else:
            # Fallback to original animation
            _expand_fallback()

    async def _expand_fallback():
        # Usar as animações nativas da janela em vez de fade/change/fade
        # As animações de tamanho e posição já estão configuradas com 800ms e EASE_IN_OUT_CUBIC
        
        # Configurar conteúdo imediatamente
        page.app_container.opacity = 1
        page.mini_icon.visible = False
        app.apply_translucency(update_page=False)
        
        # Animar posição e tamanho usando as animações nativas suaves
        page.window.left = base_left_large
        page.window.width = scale_func(650)
        page.window.height = scale_func(900)
        page.update()  # Trigger animations
        
        # Aguardar o fim da animação (800ms + margem)
        def finish_animation():
            time.sleep(0.9)  # Aguarda animação terminar
            page.is_animating = False
        
        threading.Thread(target=finish_animation, daemon=True).start()

    # --- Reduzir ---
    def shrink():
        if page.is_animating:
            return

        page.is_animating = True
        
        # Use AnimationManager if available
        if hasattr(app, 'animation_manager') and app.animation_manager:
            def _on_complete():
                page.is_animating = False
            
            try:
                future = app.animation_manager.request_play(
                    'window_shrink',
                    target_control=None,  # Not used for window animations
                    duration=0.3,
                    base_left_small=base_left_small,
                    scale_func=scale_func,
                    app_instance=app
                )
                # Schedule completion callback
                if future:
                    def _wait_complete():
                        try:
                            future.result(timeout=2.0)
                        except Exception:
                            pass
                        finally:
                            _on_complete()
                    threading.Thread(target=_wait_complete, daemon=True).start()
                else:
                    _on_complete()
            except Exception:
                # Fallback to original animation
                _shrink_fallback()
        else:
            # Fallback to original animation
            _shrink_fallback()

    def _shrink_fallback():
        # Fechar dialog de configurações se estiver aberto
        if app.settings_dialog.open:
            app.settings_dialog.open = False
            page.update()
            time.sleep(0.1)  # Pequena pausa para fechar dialog
        
        # Usar as animações nativas da janela em vez de fade/change/fade
        # As animações de tamanho e posição já estão configuradas com 800ms e EASE_IN_OUT_CUBIC
        
        # Configurar conteúdo imediatamente 
        page.app_container.opacity = 0
        page.mini_icon.visible = True
        app.apply_translucency(update_page=False)
        
        # Animar posição e tamanho usando as animações nativas suaves
        page.window.left = base_left_small
        page.window.width = scale_func(100)
        page.window.height = scale_func(100)
        page.update()  # Trigger animations
        
        # Aguardar o fim da animação (800ms + margem)
        def finish_animation():
            time.sleep(0.9)  # Aguarda animação terminar
            page.is_animating = False
        
        threading.Thread(target=finish_animation, daemon=True).start()

    # --- Reduzir Inicial (sem animação) ---
    def initial_shrink():
        page.window.left = base_left_small
        page.window.width = scale_func(100)
        page.window.height = scale_func(100)
        page.app_container.opacity = 0
        page.mini_icon.visible = True
        app.apply_translucency() # This will set window opacity
        page.update()

    # --- Checagem do mouse ---
    last_state = None  # Track last window state to prevent unnecessary toggles
    
    def check_mouse():
        nonlocal last_state
        
        while True:
            time.sleep(0.1)  # Check 10 times per second for stability
            try:
                # Don't shrink if pinned, animating, or a picker is open
                if page.pinned or page.is_animating or page.is_picker_open or page.is_file_picker_open:
                    continue

                mx, my = pyautogui.position()
                x0, y0 = page.window.left, page.window.top
                x1, y1 = x0 + page.window.width, y0 + page.window.height

                is_large_window = page.app_container.opacity == 1
                
                # Add margins to prevent flickering when cursor is near edges
                if not is_large_window:
                    # For small window, use precise rectangular detection without expansion
                    # Only expand when cursor is actually inside the small window
                    inside = x0 <= mx <= x1 and y0 <= my <= y1
                else:
                    # For large window, add margin to prevent immediate closing
                    margin = 15  # 15px margin around window
                    inside = (x0 - margin) <= mx <= (x1 + margin) and (y0 - margin) <= my <= (y1 + margin)

                # Only trigger if state actually changed
                current_state = 'large' if is_large_window else 'small'
                should_expand = inside and not is_large_window
                should_shrink = not inside and is_large_window
                
                if should_expand and last_state != 'expanding':
                    last_state = 'expanding'
                    # Use run_threadsafe to prevent UI update crashes from a background thread
                    if hasattr(page, "run_threadsafe"):
                        page.run_threadsafe(expand)
                    else:
                        expand()
                elif should_shrink and last_state != 'shrinking':
                    last_state = 'shrinking'
                    if hasattr(page, "run_threadsafe"):
                        page.run_threadsafe(shrink)
                    else:
                        shrink()
                elif not should_expand and not should_shrink:
                    # Reset state when no action needed
                    if last_state in ['expanding', 'shrinking']:
                        last_state = current_state

            except Exception as e:
                print(f"Mouse check error: {e}")

    initial_shrink()
    page.window.visible = True
    page.update()
    
    # Define o ícone da janela após ela ser criada
    def set_icon_delayed():
        """Tenta definir o ícone com múltiplas estratégias"""
        success = False
        
        # Primeira tentativa com título atual
        for attempt in range(3):
            time.sleep(0.5 + (attempt * 0.3))
            if set_window_icon("Todo APP", "list.ico"):
                success = True
                print(f"Ícone definido com sucesso na tentativa {attempt + 1}")
                break
        
        # Segunda tentativa com diferentes títulos se a primeira falhou
        if not success:
            titles_to_try = ["TODO", "Flet", "main.py"]
            for title in titles_to_try:
                time.sleep(0.5)
                if set_window_icon(title, "list.ico"):
                    success = True
                    print(f"Ícone definido com título: {title}")
                    break
        
        # Última tentativa após mais tempo
        if not success:
            time.sleep(2.0)
            set_window_icon("Todo APP", "list.ico")
    
    # Executa a definição do ícone em background
    threading.Thread(target=set_icon_delayed, daemon=True).start()

    threading.Thread(target=check_mouse, daemon=True).start()


if __name__ == "__main__":
    ft.app(target=main)