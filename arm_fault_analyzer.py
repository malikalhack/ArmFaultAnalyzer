#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 ******************************************************************************
 * @file    arm_fault_analyzer.py
 * @version 1.3.0
 * @author  Anton Chernov
 * @date    04/23/2026
 * @brief   ARM Cortex-M Fault Analyzer with GUI
 *
 * @details A tool for detailed analysis of system faults on ARM Cortex-M
 *          microcontrollers (M0/M0+/M3/M4/M7).
 *
 *          Supported fault types:
 *          - HardFault    : critical processor fault
 *          - MemManage    : memory protection violation (MPU)
 *          - BusFault     : bus error (invalid address)
 *          - UsageFault   : illegal instruction or processor state
 *          - Debug Fault  : debug event
 *
 *          Analysed registers:
 *          - R0-R3, R12, LR, PC, PSR : processor state
 *          - CFSR  : Configurable Fault Status Register (MMFSR/BFSR/UFSR)
 *          - HFSR  : HardFault Status Register
 *          - DFSR  : Debug Fault Status Register
 *          - AFSR  : Auxiliary Fault Status Register
 *          - BFAR  : BusFault Address Register
 *          - MMFAR : MemManage Fault Address Register
 *
 *******************************************************************************
"""

################################ Импорт модулей ################################
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
import sys
import subprocess
import re
from datetime import datetime

################################################################################
#                              Версия приложения                               #
################################################################################

APP_VERSION = "1.3.0"

def get_version() -> str:
    """Return the application version string."""
    return APP_VERSION

def validate_py_version() -> bool:
    """
    @brief  Check that the interpreter meets the minimum version requirement.

    @return True if Python >= 3.8, False otherwise.
    """
    bool_result = True
    major_version = sys.version_info.major
    minor_version = sys.version_info.minor
    if not (major_version == 3 and minor_version >= 8):
        print("Python 3.8 or higher is required.")
        print(f"You are using Python {major_version}.{minor_version}")
        bool_result = False
    return bool_result

################################################################################
#                             Локализация                                      #
################################################################################

_strings = {}

def _load_locale(lang: str) -> None:
    """
    Load locale strings from Locales/<lang>.json; fall back to 'ru' on error.
    """
    global _strings
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, 'Locales', f'{lang}.json')
    ret_val = False
    try:
        with open(path, 'r', encoding='utf-8') as f:
            _strings = json.load(f)
        ret_val = True
    except Exception:
        ret_val = False
    if not ret_val and lang != 'ru':
        # Fallback на русский язык
        _load_locale('ru')

def t(key: str, **kwargs) -> str:
    """Return localised string for *key*, with optional format arguments."""
    template = _strings.get(key, key)
    ret_val = template
    if kwargs:
        try:
            ret_val = template.format(**kwargs)
        except (KeyError, ValueError):
            ret_val = template
    return ret_val

################################################################################
#                        Класс ARM Fault Analyzer                             #
################################################################################

class ARMFaultAnalyzer:
    """
    @brief  Main GUI class for the ARM Cortex-M fault register analyzer

    @details Provides a complete fault analysis workflow:
             - Manual register input or loading from a JSON dump file
             - Bit-field decoding of CFSR, HFSR, DFSR, AFSR, PSR
             - Fault cause interpretation with remediation recommendations
             - Analysis history with save/restore support
             - Configurable default paths for file dialogs
    """

    @staticmethod
    def _get_app_dir() -> str:
        """
        @brief  Return the OS-standard application data directory,
                creating it on first use.

        @details
                 - Windows : %APPDATA%\\ARMFaultAnalyzer\\
                 - Linux / macOS : ~/.config/ARMFaultAnalyzer/

        @return  Absolute path to the application data directory.
        """
        if sys.platform == "win32":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            base = os.path.join(os.path.expanduser("~"), ".config")
        app_dir = os.path.join(base, "ARMFaultAnalyzer")
        os.makedirs(app_dir, exist_ok=True)
        return app_dir

    def __init__(self, root):
        """
        @brief  Initialize the main application window

        @param[in]  root  Tkinter root window object
        """
        self.root = root
        self.root.title("ARM Cortex-M Fault Analyzer")
        self.root.geometry("1100x870")

        # Конфигурационный файл — всегда в каталоге данных приложения
        _app_dir = self._get_app_dir()
        self.config_file = os.path.join(_app_dir, "arm_analyzer_config.json")

        # Настройки по умолчанию
        self.settings = {
            'default_load_path': '',
            'default_save_path': '',
            'history_dir': '',          # '' → тот же каталог, что и конфиг
            'recent_map_files': [],
            'recent_json_files': [],
            'recent_files_limit': 5,
            'history_limit': 50,
            'language': 'ru'
        }
        self.load_settings()

        # Вычисляем путь к файлу истории заранее (нужен в create_settings_tab)
        history_dir = self.settings.get('history_dir', '').strip()
        if not history_dir or not os.path.isdir(history_dir):
            history_dir = os.path.dirname(self.config_file)
        self.history_file = os.path.join(history_dir, "arm_analyzer_history.json")

        # Загрузка локали (язык берётся из конфига, по умолчанию 'ru')
        _load_locale(self.settings.get('language', 'ru'))

        self.root.title(t('app_title'))

        # Нижняя полоска с кнопкой версии (pack до notebook, чтобы не было вытеснена)
        bottom_bar = ttk.Frame(root)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0, 3))
        ttk.Button(
            bottom_bar,
            text=f"v{APP_VERSION}",
            command=self.show_about,
            width=8
        ).pack(side=tk.LEFT)

        # Создание вкладок
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Вкладка анализа
        self.analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_frame, text=t('tab_analysis'))

        # Вкладка истории
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text=t('tab_history'))

        # Вкладка настроек
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text=t('tab_settings'))

        # Вкладка помощи
        self.help_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.help_frame, text=t('tab_help'))

        # Инициализация UI
        self.create_analysis_tab()
        self.create_history_tab()
        self.create_settings_tab()
        self.create_help_tab()

        # История анализов
        self.analysis_history = []
        self.map_symbols = []
        self._load_history()

    def show_about(self):
        """Show the About dialog with version and author information."""
        messagebox.showinfo(
            t('about_title'),
            t('about_text', version=APP_VERSION)
        )

    def create_analysis_tab(self):
        """Create the register analysis tab."""

        # Левая панель - ввод регистров
        left_panel = ttk.Frame(self.analysis_frame)
        left_panel.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=False,
            padx=5,
            pady=5
        )

        # Правая панель - результаты
        right_panel = ttk.Frame(self.analysis_frame)
        right_panel.pack(
            side=tk.RIGHT,
            fill=tk.BOTH,
            expand=True,
            padx=5,
            pady=5
        )

        # === ЛЕВАЯ ПАНЕЛЬ ===

        # Основные регистры
        core_frame = ttk.LabelFrame(
            left_panel,
            text=t('group_core_regs'),
            padding=10
        )
        core_frame.pack(fill=tk.X, pady=5)

        self.reg_entries = {}
        core_regs = [
            ("R0", "0x00000000"),
            ("R1", "0x00000000"),
            ("R2", "0x00000000"),
            ("R3", "0x00000000"),
            ("R12", "0x00000000"),
            ("SP",  "0x20000000"),
            ("LR", "0x00000000"),
            ("PC", "0x00000000"),
            ("PSR", "0x01000000"),
        ]

        for reg_name, default_val in core_regs:
            frame = ttk.Frame(core_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=f"{reg_name}:", width=6).pack(side=tk.LEFT)
            entry = ttk.Entry(frame, width=20)
            entry.insert(0, default_val)
            entry.pack(side=tk.LEFT, padx=5)
            self.reg_entries[reg_name] = entry

        # Fault Status регистры
        fault_frame = ttk.LabelFrame(
            left_panel,
            text=t('group_fault_regs'),
            padding=10
        )
        fault_frame.pack(fill=tk.X, pady=5)

        fault_regs = [
            ("CFSR",  "0x00000000", t('tooltip_cfsr')),
            ("HFSR",  "0x00000000", t('tooltip_hfsr')),
            ("DFSR",  "0x00000000", t('tooltip_dfsr')),
            ("AFSR",  "0x00000000", t('tooltip_afsr')),
            ("BFAR",  "0x00000000", t('tooltip_bfar')),
            ("MMFAR", "0x00000000", t('tooltip_mmfar')),
        ]

        for reg_name, default_val, tooltip in fault_regs:
            frame = ttk.Frame(fault_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=f"{reg_name}:", width=8).pack(side=tk.LEFT)
            entry = ttk.Entry(frame, width=18)
            entry.insert(0, default_val)
            entry.pack(side=tk.LEFT, padx=5)
            self.reg_entries[reg_name] = entry

            # Всплывающая подсказка
            label = ttk.Label(frame, text="?", foreground="blue", cursor="hand2")
            label.pack(side=tk.LEFT)
            self.create_tooltip(label, tooltip)

        # Кнопки управления
        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(
            btn_frame,
            text=t('btn_analyze'),
            command=self.analyze_fault
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            btn_frame,
            text=t('btn_clear'),
            command=self.clear_fields
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            btn_frame,
            text=t('btn_load_file'),
            command=self.load_from_file
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            btn_frame,
            text=t('btn_save_result'),
            command=self.save_results
        ).pack(fill=tk.X, pady=2)

        # MAP файл для определения функции по адресу PC
        map_frame = ttk.LabelFrame(
            left_panel,
            text=t('group_map_file'),
            padding=10
        )
        map_frame.pack(fill=tk.X, pady=5)

        map_row = ttk.Frame(map_frame)
        map_row.pack(fill=tk.X)

        self.map_file_combo = ttk.Combobox(
            map_row,
            values=self.settings.get('recent_map_files', [])
        )
        self.map_file_combo.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
            padx=(0, 3)
        )
        self.map_file_combo.bind(
            '<<ComboboxSelected>>',
            self._on_map_combo_select
        )

        ttk.Button(
            map_row,
            text=t('btn_browse'),
            command=self.browse_map_file
        ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(
            map_row,
            text=t('btn_clear_map'),
            command=self.clear_map_file,
            width=2
        ).pack(side=tk.LEFT)

        self.map_status_label = ttk.Label(
            map_frame,
            text=t('map_not_loaded'),
            foreground="gray"
        )
        self.map_status_label.pack(anchor=tk.W, pady=(5, 0))

        # === ПРАВАЯ ПАНЕЛЬ ===

        # Декодированные флаги
        decode_frame = ttk.LabelFrame(
            right_panel,
            text=t('group_decoded'),
            padding=5
        )
        decode_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.decode_text = scrolledtext.ScrolledText(
            decode_frame,
            height=26,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.decode_text.pack(fill=tk.BOTH, expand=True)

        # Результаты анализа
        results_frame = ttk.LabelFrame(
            right_panel,
            text=t('group_diagnosis'),
            padding=5
        )
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            height=15,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(
            results_frame,
            text=t('btn_copy_diag'),
            command=self.copy_diagnosis
        ).pack(anchor=tk.E, pady=(3, 0))

        # Настройка цветовых тегов
        self.decode_text.tag_config(
            "error",
            foreground="red",
            font=("Consolas", 9, "bold")
        )
        self.decode_text.tag_config("warning", foreground="orange")
        self.decode_text.tag_config("info", foreground="blue")
        self.decode_text.tag_config("ok", foreground="green")

        self.results_text.tag_config(
            "error",
            foreground="red",
            font=("Consolas", 9, "bold")
        )
        self.results_text.tag_config(
            "warning",
            foreground="orange",
            font=("Consolas", 9, "bold")
        )
        self.results_text.tag_config("info", foreground="blue")

    def create_history_tab(self):
        """Create the history tab."""

        # Список истории
        self.history_listbox = tk.Listbox(self.history_frame, height=10)
        self.history_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.history_listbox.bind('<<ListboxSelect>>', self.on_history_select)

        # Детали выбранного анализа
        details_frame = ttk.LabelFrame(
            self.history_frame,
            text=t('hist_details'),
            padding=5
        )
        details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.history_text = scrolledtext.ScrolledText(
            details_frame,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.history_text.pack(fill=tk.BOTH, expand=True)

        # Кнопки
        btn_frame = ttk.Frame(self.history_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            btn_frame,
            text=t('btn_restore'),
            command=self.restore_from_history
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            btn_frame,
            text=t('btn_clear_hist'),
            command=self.clear_history
        ).pack(side=tk.LEFT, padx=2)

    def create_settings_tab(self):
        """Create the settings tab."""

        main_frame = ttk.Frame(self.settings_frame, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        title_label = ttk.Label(
            main_frame,
            text=t('settings_title'),
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Пути по умолчанию
        paths_frame = ttk.LabelFrame(
            main_frame,
            text=t('settings_paths'),
            padding=15
        )
        paths_frame.pack(fill=tk.X, pady=10)

        # Путь для загрузки
        load_frame = ttk.Frame(paths_frame)
        load_frame.pack(fill=tk.X, pady=5)
        ttk.Label(
            load_frame,
            text=t('settings_load_path'),
            width=28
        ).pack(side=tk.LEFT)
        self.load_path_entry = ttk.Entry(load_frame, width=60)
        self.load_path_entry.pack(side=tk.LEFT, padx=5)
        self.load_path_entry.insert(0, self.settings['default_load_path'])
        ttk.Button(
            load_frame,
            text=t('btn_browse'),
            command=lambda: self.browse_directory(self.load_path_entry)
        ).pack(side=tk.LEFT)

        # Путь для сохранения
        save_frame = ttk.Frame(paths_frame)
        save_frame.pack(fill=tk.X, pady=5)
        ttk.Label(
            save_frame,
            text=t('settings_save_path'),
            width=28
        ).pack(side=tk.LEFT)
        self.save_path_entry = ttk.Entry(save_frame, width=60)
        self.save_path_entry.pack(side=tk.LEFT, padx=5)
        self.save_path_entry.insert(0, self.settings['default_save_path'])
        ttk.Button(
            save_frame,
            text=t('btn_browse'),
            command=lambda: self.browse_directory(self.save_path_entry)
        ).pack(side=tk.LEFT)

        # Каталог файла истории
        hist_dir_frame = ttk.Frame(paths_frame)
        hist_dir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(
            hist_dir_frame,
            text=t('settings_hist_dir'),
            width=28
        ).pack(side=tk.LEFT)
        self.hist_dir_entry = ttk.Entry(hist_dir_frame, width=60)
        self.hist_dir_entry.pack(side=tk.LEFT, padx=5)
        self.hist_dir_entry.insert(0, self.settings.get('history_dir', ''))
        ttk.Button(
            hist_dir_frame,
            text=t('btn_browse'),
            command=lambda: self.browse_directory(self.hist_dir_entry)
        ).pack(side=tk.LEFT)

        # Язык интерфейса
        lang_frame = ttk.Frame(paths_frame)
        lang_frame.pack(fill=tk.X, pady=5)
        ttk.Label(
            lang_frame,
            text=t('settings_language'),
            width=28
        ).pack(side=tk.LEFT)
        self.lang_combo = ttk.Combobox(
            lang_frame,
            values=['ru', 'en'],
            width=8,
            state='readonly'
        )
        self.lang_combo.set(self.settings.get('language', 'ru'))
        self.lang_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            lang_frame,
            text=t('settings_restart_note'),
            foreground='gray'
        ).pack(side=tk.LEFT, padx=6)

        # Кнопки управления
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(
            btn_frame,
            text=t('btn_save_settings'),
            command=self.save_settings_ui
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame,
            text=t('btn_reset_settings'),
            command=self.reset_settings
        ).pack(side=tk.LEFT, padx=5)

        # Ограничения размеров
        limits_frame = ttk.LabelFrame(
            main_frame,
            text=t('settings_limits'),
            padding=15
        )
        limits_frame.pack(fill=tk.X, pady=(0, 10))

        lim1_frame = ttk.Frame(limits_frame)
        lim1_frame.pack(fill=tk.X, pady=3)
        ttk.Label(
            lim1_frame,
            text=t('settings_recent_limit'),
            width=32
        ).pack(side=tk.LEFT)
        self.recent_limit_spin = ttk.Spinbox(lim1_frame, from_=1, to=20, width=5)
        self.recent_limit_spin.set(self.settings.get('recent_files_limit', 5))
        self.recent_limit_spin.pack(side=tk.LEFT)
        ttk.Label(
            lim1_frame,
            text=t('settings_recent_hint'),
            foreground="gray"
        ).pack(side=tk.LEFT, padx=6)

        lim2_frame = ttk.Frame(limits_frame)
        lim2_frame.pack(fill=tk.X, pady=3)
        ttk.Label(
            lim2_frame,
            text=t('settings_hist_limit'),
            width=32
        ).pack(side=tk.LEFT)
        self.history_limit_spin = ttk.Spinbox(
            lim2_frame,
            from_=10,
            to=500,
            width=5
        )
        self.history_limit_spin.set(self.settings.get('history_limit', 50))
        self.history_limit_spin.pack(side=tk.LEFT)

        # Информация о конфигурационном файле
        info_frame = ttk.LabelFrame(
            main_frame,
            text=t('settings_info'),
            padding=10
        )
        info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(
            info_frame,
            text=t(
                'settings_config_path',
                path=os.path.normpath(os.path.abspath(self.config_file))
            ),
            font=("Consolas", 8),
            foreground="gray"
        ).pack(anchor=tk.W)
        ttk.Label(
            info_frame,
            text=t(
                'settings_history_path',
                path=os.path.normpath(os.path.abspath(self.history_file))
            ),
            font=("Consolas", 8),
            foreground="gray"
        ).pack(anchor=tk.W)
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        _raw_lp = self.settings.get('default_load_path', '')
        _load_p = (
            os.path.normpath(_raw_lp) if _raw_lp
            else _script_dir
        )
        self._info_load_var = tk.StringVar(
            value=t('settings_load_path_info', path=_load_p)
        )
        ttk.Label(
            info_frame,
            textvariable=self._info_load_var,
            font=("Consolas", 8),
            foreground="gray"
        ).pack(anchor=tk.W)
        _raw_sp = self.settings.get('default_save_path', '')
        _save_p = (
            os.path.normpath(_raw_sp) if _raw_sp
            else _script_dir
        )
        self._info_save_var = tk.StringVar(
            value=t('settings_save_path_info', path=_save_p)
        )
        ttk.Label(
            info_frame,
            textvariable=self._info_save_var,
            font=("Consolas", 8),
            foreground="gray"
        ).pack(anchor=tk.W)

    def create_help_tab(self):
        """Create the help tab."""

        help_text = scrolledtext.ScrolledText(
            self.help_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=10,
            pady=10
        )
        help_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        lang = self.settings.get('language', 'ru')
        base_dir = os.path.dirname(os.path.abspath(__file__))
        help_path = os.path.join(base_dir, 'Locales', f'help_{lang}.txt')
        # Fallback на русский, если файл для выбранного языка отсутствует
        if not os.path.exists(help_path):
            help_path = os.path.join(base_dir, 'Locales', 'help_ru.txt')

        help_content = ""
        try:
            with open(help_path, 'r', encoding='utf-8') as f:
                help_content = f.read()
        except Exception:
            help_content = f"[Help file not found: {help_path}]"

        help_text.insert(1.0, help_content)
        help_text.config(state=tk.DISABLED)

        # Настройка цветовых тегов
        help_text.tag_config("header", font=("Consolas", 11, "bold"))

    def browse_directory(self, entry_widget):
        """Open a directory chooser dialog and update the entry widget."""
        directory = filedialog.askdirectory(
            title=t('dlg_choose_dir'),
            initialdir=entry_widget.get() if entry_widget.get() else os.getcwd()
        )
        if directory:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, os.path.normpath(directory))

    def _on_map_combo_select(self, event):
        """
        Auto-load the MAP file when an item is selected from the combo box.
        """
        path = self.map_file_combo.get().strip()
        if path and os.path.exists(path):
            self.load_map_file(path)

    def browse_map_file(self):
        """Open a file dialog to select a MAP file and load it immediately."""
        initial_dir = self.settings.get('default_load_path', '')
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        filename = filedialog.askopenfilename(
            title=t('dlg_open_map'),
            initialdir=initial_dir,
            filetypes=[("MAP files", "*.map"), ("All files", "*.*")]
        )
        if filename:
            self._add_to_recent_map(filename)
            self.map_file_combo.set(filename)
            self.load_map_file(filename)

    def clear_map_file(self):
        """Clear the currently loaded MAP file."""
        self.map_file_combo.set('')
        self.map_symbols = []
        self.map_status_label.config(text=t('map_not_loaded'), foreground="gray")

    def load_settings(self):
        """Load settings from the config file."""
        ret_val = None
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.settings = json.load(f)
                ret_val = True
            else:
                ret_val = False
        except Exception:
            ret_val = False
        return ret_val

    def save_settings_ui(self):
        """
        Read settings from the UI controls and save them to the config file.
        """
        old_lang = self.settings.get('language', 'ru')
        self.settings['default_load_path'] = self.load_path_entry.get()
        self.settings['default_save_path'] = self.save_path_entry.get()
        self.settings['history_dir'] = self.hist_dir_entry.get().strip()
        self.settings['language'] = self.lang_combo.get()
        try:
            self.settings['recent_files_limit'] = int(self.recent_limit_spin.get())
        except ValueError:
            pass
        try:
            self.settings['history_limit'] = int(self.history_limit_spin.get())
        except ValueError:
            pass

        ret_val = None
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            new_lang = self.settings['language']
            if new_lang != old_lang:
                messagebox.showinfo(t('msg_success'), t('msg_restart_required'))
                self._restart_app()
            else:
                self._update_info_labels()
                messagebox.showinfo(t('msg_success'), t('msg_settings_saved'))
            ret_val = True
        except Exception as e:
            messagebox.showerror(t('msg_error'), t('msg_settings_error', error=e))
            ret_val = False
        return ret_val

    def reset_settings(self):
        """Reset all settings to their default values."""
        if messagebox.askyesno(t('dlg_confirm'), t('dlg_reset_confirm')):
            self.load_path_entry.delete(0, tk.END)
            self.save_path_entry.delete(0, tk.END)
            self.hist_dir_entry.delete(0, tk.END)
            self.settings['default_load_path'] = ''
            self.settings['default_save_path'] = ''
            self.settings['history_dir'] = ''
            self.recent_limit_spin.set(5)
            self.history_limit_spin.set(50)
            self.settings['recent_files_limit'] = 5
            self.settings['history_limit'] = 50
            self._update_info_labels()
            self._autosave_settings()
            messagebox.showinfo(t('msg_success'), t('msg_settings_reset'))

    def _update_info_labels(self):
        """Refresh the load/save path labels in the Information block."""
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        _raw_lp = self.settings.get('default_load_path', '')
        _load_p = (
            os.path.normpath(_raw_lp) if _raw_lp
            else _script_dir
        )
        self._info_load_var.set(
            t('settings_load_path_info', path=_load_p)
        )
        _raw_sp = self.settings.get('default_save_path', '')
        _save_p = (
            os.path.normpath(_raw_sp) if _raw_sp
            else _script_dir
        )
        self._info_save_var.set(
            t('settings_save_path_info', path=_save_p)
        )

    def _restart_app(self):
        """
        @brief  Restart the application to apply new settings
        (e.g. language change)
        """
        self.root.destroy()
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)

    def create_tooltip(self, widget, text):
        """Attach a hover tooltip to a widget."""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = ttk.Label(
                tooltip,
                text=text,
                background="lightyellow",
                relief=tk.SOLID,
                borderwidth=1,
                padding=5
            )
            label.pack()
            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def parse_hex_value(self, value_str):
        """
        Parse a hex string (with or without '0x' prefix) and return an integer.
        """
        ret_val = None
        try:
            value_str = value_str.strip()
            if value_str.startswith('0x') or value_str.startswith('0X'):
                ret_val = int(value_str, 16)
            else:
                ret_val = int(value_str, 16)
        except ValueError:
            ret_val = 0
        return ret_val

    def load_map_file(self, path):
        """
        @brief  Parse a MAP file (GNU LD or AC6 armlink) and build a sorted
                symbol table

        @details Auto-detects the map format by scanning for format-specific
                 markers:
                 - AC6 armlink : contains 'Image Symbol Table' header;
                                 symbol lines have the form:
                                   <name>  0x<addr>  Thumb Code ...
                                   <name>  0x<addr>  ARM Code   ...
                 - GNU LD      : symbol lines have the form:
                                   <whitespace> 0x<addr> <name>
                 Builds a list sorted by address for binary search lookup.

        @param[in]  path  Absolute path to the .map file
        @return     True on success, False on failure
        """
        self.map_symbols = []
        ret_val = False

        # Паттерны регулярных выражений для обоих форматов
        gnu_pattern = re.compile(r'^\s+(0x[0-9a-fA-F]{4,})\s+([A-Za-z_]\w+)\s*$')
        ac6_pattern = re.compile(
            r'^\s+([A-Za-z_]\w+)\s+(0x[0-9a-fA-F]{8})\s+(?:Thumb|ARM)\s+Code'
        )

        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            # Автоопределение формата
            is_ac6 = any('Image Symbol Table' in line for line in lines)
            fmt_name = "AC6 armlink" if is_ac6 else "GNU LD"
            pattern = ac6_pattern if is_ac6 else gnu_pattern

            for line in lines:
                m = pattern.match(line)
                if m:
                    if is_ac6:
                        name = m.group(1)
                        addr = int(m.group(2), 16)
                    else:
                        addr = int(m.group(1), 16)
                        name = m.group(2)
                    self.map_symbols.append((addr, name))

            self.map_symbols.sort(key=lambda x: x[0])
            count = len(self.map_symbols)
            self.map_status_label.config(
                text=t('map_loaded', fmt=fmt_name, count=count),
                foreground="green"
            )
            ret_val = True
        except Exception as e:
            self.map_status_label.config(
                text=t('map_load_error', error=e),
                foreground="red"
            )
            self.map_symbols = []
            ret_val = False
        return ret_val

    def resolve_pc_to_function(self, pc):
        """
        @brief  Find the function name for a given PC address via binary search

        @details Returns the name of the function whose start address is the
                 largest address that is <= pc (i.e., pc falls inside that
                 function).

        @param[in]  pc  Program Counter value (32-bit address)
        @return     Function name string, or None if not found / table empty
        """
        ret_val = None
        if self.map_symbols:
            lo, hi = 0, len(self.map_symbols) - 1
            while lo <= hi:
                mid = (lo + hi) // 2
                if self.map_symbols[mid][0] <= pc:
                    lo = mid + 1
                else:
                    hi = mid - 1
            if hi >= 0:
                ret_val = self.map_symbols[hi][1]
        return ret_val

    def identify_memory_region(self, addr):
        """
        @brief  Identify the ARM Cortex-M memory region for a given address

        @details Uses the standard ARM Cortex-M memory map architecture:
                 Code / SRAM / Peripheral / External RAM / External Device /
                 System. STM32-specific peripheral sub-ranges are also listed.

        @param[in]  addr  32-bit address to identify
        @return     Human-readable region string
        """
        # Общие зоны памяти ARM Cortex-M
        REGIONS = [
            (0x00000000, 0x1FFFFFFF, t('region_code')),
            (0x20000000, 0x3FFFFFFF, t('region_sram')),
            (0x40000000, 0x4FFFFFFF, t('region_peripheral')),
            (0x60000000, 0x9FFFFFFF, t('region_ext_ram')),
            (0xA0000000, 0xDFFFFFFF, t('region_ext_dev')),
            (0xE0000000, 0xFFFFFFFF, t('region_system')),
        ]
        # Подзоны STM32 APB/AHB (общие для большинства семейств)
        STM32_ZONES = [
            (0x40000000, 0x40007FFF, t('region_apb1')),
            (0x40010000, 0x40017FFF, t('region_apb2')),
            (0x40020000, 0x4007FFFF, t('region_ahb1')),
            (0x50000000, 0x5FFFFFFF, t('region_ahb2')),
            (0xE0001000, 0xE0001FFF, t('region_dwt')),
            (0xE0002000, 0xE0002FFF, t('region_fpb')),
            (0xE000E000, 0xE000EFFF, t('region_scs')),
            (0xE0040000, 0xE00FFFFF, t('region_tpiu')),
        ]
        ret_val = t('region_unknown')
        # Сначала проверяем STM32 подзоны (более специфичные)
        for start, end, name in STM32_ZONES:
            if start <= addr <= end:
                ret_val = name
                break
        else:
            for start, end, name in REGIONS:
                if start <= addr <= end:
                    ret_val = name
                    break
        return ret_val

    def identify_magic_value(self, val):
        """
        @brief  Check if a value matches a known embedded magic constant

        @details Recognizes common MCU magic values: stack fill patterns,
                 IWDG/WWDG keys, debug markers, null pointer, etc.

        @param[in]  val  32-bit register value
        @return     Description string, or None if not a known constant
        """
        MAGIC = {
            0x00000000: "NULL pointer",
            0xDEADBEEF: "Debug marker (DEADBEEF)",
            0xA5A5A5A5: "Stack fill pattern (Keil/AC6)",
            0xCCCCCCCC: "Stack fill pattern (IAR)",
            0x55555555: "Stack fill pattern",
            0xFEFEFEFE: "Uninitialised heap marker",
            0x10101010: "Initial stack frame marker (task never ran)",
            0x11111111: "Initial stack frame marker (task never ran)",
            0x12121212: "Initial stack frame marker (task never ran)",
            0x33333333: "Initial stack frame marker (task never ran)",
            0x44444444: "Initial stack frame marker (task never ran)",
            0x66666666: "Initial stack frame marker (task never ran)",
            0x77777777: "Initial stack frame marker (task never ran)",
            0x88888888: "Initial stack frame marker (task never ran)",
            0x99999999: "Initial stack frame marker (task never ran)",
            # Ключи IWDG
            0x00005555: "IWDG_KEY_WRITE_ACCESS (0x5555)",
            0x0000CCCC: "IWDG_KEY_ENABLE (0xCCCC)",
            0x0000AAAA: "IWDG_KEY_RELOAD (0xAAAA)",
            # WWDG
            0x0000FF00: "WWDG reset value",
            # Ключи разблокировки Flash
            0x45670123: "FLASH unlock key 1",
            0xCDEF89AB: "FLASH unlock key 2",
            # Значение сброса RCC
            0xFFFFFFFF: "All bits set (possible uninitialized / erased Flash)",
        }
        return MAGIC.get(val, None)

    def decode_exc_return(self, lr):
        """
        @brief  Decode EXC_RETURN value in LR register

        @details When the processor enters an exception handler, LR is loaded with
                 a special EXC_RETURN value (bits [31:4] = 0xFFFFFFF or 0xFFFFFFE).
                 Bits [3:0] encode the return mode, stack pointer, and FPU state.

        @param[in]  lr  Link Register value (32-bit)
        @return     Description string if lr is a valid EXC_RETURN, None otherwise
        """
        EXC_RETURN_MAP = {
            0xFFFFFFF1: "Handler mode → Handler mode, MSP, no FPU",
            0xFFFFFFF9: "Handler mode → Thread mode,  MSP, no FPU",
            0xFFFFFFFD: "Handler mode → Thread mode,  PSP, no FPU",
            0xFFFFFFE1: "Handler mode → Handler mode, MSP, FPU active",
            0xFFFFFFE9: "Handler mode → Thread mode,  MSP, FPU active",
            0xFFFFFFED: "Handler mode → Thread mode,  PSP, FPU active",
        }
        return EXC_RETURN_MAP.get(lr, None)

#-------------------------------------------------------------------------------
# Функции декодирования регистров статуса ошибок
#-------------------------------------------------------------------------------

    def decode_cfsr(self, cfsr_value):
        """
        @brief  Decode CFSR register (Configurable Fault Status Register)

        @details CFSR combines three fault status registers:
                 - MMFSR [7:0]   : MemManage Fault Status Register
                 - BFSR  [15:8]  : BusFault Status Register
                 - UFSR  [31:16] : UsageFault Status Register

        @param[in]  cfsr_value  CFSR register value (32-bit)
        @return     List of strings with decoded fault flags
        """
        ret_val = []

        # MMFSR (bits 0-7) - MemManage Fault Status Register
        mmfsr = cfsr_value & 0xFF
        ret_val.append(t('decode_mmfsr_header'))

        if mmfsr & (1 << 0):
            ret_val.append(t('decode_mmfsr_iaccviol'))
        if mmfsr & (1 << 1):
            ret_val.append(t('decode_mmfsr_daccviol'))
        if mmfsr & (1 << 3):
            ret_val.append(t('decode_mmfsr_munstkerr'))
        if mmfsr & (1 << 4):
            ret_val.append(t('decode_mmfsr_mstkerr'))
        if mmfsr & (1 << 5):
            ret_val.append(t('decode_mmfsr_mlsperr'))
        if mmfsr & (1 << 7):
            ret_val.append(t('decode_mmfsr_mmarvalid'))

        if mmfsr == 0:
            ret_val.append(t('decode_mmfsr_ok'))

        # BFSR (bits 8-15) - BusFault Status Register
        bfsr = (cfsr_value >> 8) & 0xFF
        ret_val.append("\n" + t('decode_bfsr_header'))

        if bfsr & (1 << 0):
            ret_val.append(t('decode_bfsr_ibuserr'))
        if bfsr & (1 << 1):
            ret_val.append(t('decode_bfsr_preciserr'))
        if bfsr & (1 << 2):
            ret_val.append(t('decode_bfsr_impreciserr'))
        if bfsr & (1 << 3):
            ret_val.append(t('decode_bfsr_unstkerr'))
        if bfsr & (1 << 4):
            ret_val.append(t('decode_bfsr_stkerr'))
        if bfsr & (1 << 5):
            ret_val.append(t('decode_bfsr_lsperr'))
        if bfsr & (1 << 7):
            ret_val.append(t('decode_bfsr_bfarvalid'))

        if bfsr == 0:
            ret_val.append(t('decode_bfsr_ok'))

        # UFSR (bits 16-31) - UsageFault Status Register
        ufsr = (cfsr_value >> 16) & 0xFFFF
        ret_val.append("\n" + t('decode_ufsr_header'))

        if ufsr & (1 << 0):
            ret_val.append(t('decode_ufsr_undefinstr'))
        if ufsr & (1 << 1):
            ret_val.append(t('decode_ufsr_invstate'))
        if ufsr & (1 << 2):
            ret_val.append(t('decode_ufsr_invpc'))
        if ufsr & (1 << 3):
            ret_val.append(t('decode_ufsr_nocp'))
        if ufsr & (1 << 8):
            ret_val.append(t('decode_ufsr_unaligned'))
        if ufsr & (1 << 9):
            ret_val.append(t('decode_ufsr_divbyzero'))

        if ufsr == 0:
            ret_val.append(t('decode_ufsr_ok'))

        return ret_val

    def decode_hfsr(self, hfsr_value):
        """
        @brief  Decode HFSR register (HardFault Status Register)

        @details Contains information about critical processor faults.
                 The FORCED bit indicates escalation from a lower-priority fault
                 (MemManage / BusFault / UsageFault).

        @param[in]  hfsr_value  HFSR register value (32-bit)
                                Bit 30: FORCED   - escalated from another fault
                                Bit 1:  VECTTBL  - vector table bus fault
                                Bit 31: DEBUGEVT - debug event
        @return     List of strings with decoded fault flags
        """
        ret_val = []
        ret_val.append(t('decode_hfsr_header'))

        if hfsr_value & (1 << 1):
            ret_val.append(t('decode_hfsr_vecttbl'))
        if hfsr_value & (1 << 30):
            ret_val.append(t('decode_hfsr_forced'))
        if hfsr_value & (1 << 31):
            ret_val.append(t('decode_hfsr_debugevt'))

        if hfsr_value == 0:
            ret_val.append(t('decode_hfsr_ok'))

        return ret_val

    def decode_dfsr(self, dfsr_value):
        """
        @brief  Decode DFSR register (Debug Fault Status Register)

        @details Contains debug event status flags:
                 - HALTED, BKPT, DWTTRAP, VCATCH, EXTERNAL

        @param[in]  dfsr_value  DFSR register value (32-bit)
        @return     List of strings with decoded fault flags
        """
        ret_val = []
        ret_val.append(t('decode_dfsr_header'))

        if dfsr_value & (1 << 0):
            ret_val.append(t('decode_dfsr_halted'))
        if dfsr_value & (1 << 1):
            ret_val.append(t('decode_dfsr_bkpt'))
        if dfsr_value & (1 << 2):
            ret_val.append(t('decode_dfsr_dwttrap'))
        if dfsr_value & (1 << 3):
            ret_val.append(t('decode_dfsr_vcatch'))
        if dfsr_value & (1 << 4):
            ret_val.append(t('decode_dfsr_external'))

        if dfsr_value == 0:
            ret_val.append(t('decode_dfsr_ok'))

        return ret_val

    def decode_afsr(self, afsr_value):
        """
        @brief  Decode AFSR register (Auxiliary Fault Status Register)

        @details Implementation-defined register.
                 Interpretation depends on the MCU vendor (ST, NXP, TI, etc.)

        @param[in]  afsr_value  AFSR register value (32-bit)
        @return     List of strings with decoded fault flags
        """
        ret_val = []
        ret_val.append(t('decode_afsr_header'))

        if afsr_value == 0:
            ret_val.append(t('decode_afsr_ok'))
        else:
            ret_val.append(t('decode_afsr_value', value=afsr_value))
            ret_val.append(t('decode_afsr_info'))

        return ret_val

    def decode_psr(self, psr_value):
        """
        @brief  Decode PSR register (Program Status Register)

        @details Program Status Register contains:
                 - APSR flags [31:28] : N, Z, C, V arithmetic condition flags
                 - Exception number [8:0] : current exception/interrupt number
                 - T bit [24] : Thumb state (must be 1 on Cortex-M)

        @param[in]  psr_value  PSR register value (32-bit)
        @return     List of strings with decoded flags
        """
        ret_val = []
        ret_val.append(t('decode_psr_header'))

        # APSR флаги
        ret_val.append(t('decode_psr_apsr'))
        ret_val.append(t('decode_psr_n', val=(psr_value >> 31) & 1))
        ret_val.append(t('decode_psr_z', val=(psr_value >> 30) & 1))
        ret_val.append(t('decode_psr_c', val=(psr_value >> 29) & 1))
        ret_val.append(t('decode_psr_v', val=(psr_value >> 28) & 1))
        ret_val.append(t('decode_psr_q', val=(psr_value >> 27) & 1))

        # Номер текущего ISR
        isr_num = psr_value & 0x1FF
        ISR_NAMES = {
            0:  t('isr_thread'),
            2:  t('isr_nmi'),
            3:  t('isr_hardfault'),
            4:  t('isr_memmanage'),
            5:  t('isr_busfault'),
            6:  t('isr_usagefault'),
            11: t('isr_svcall'),
            12: t('isr_debugmon'),
            14: t('isr_pendsv'),
            15: t('isr_systick'),
        }
        if isr_num in ISR_NAMES:
            isr_str = ISR_NAMES[isr_num]
        elif isr_num >= 16:
            isr_str = t('decode_psr_irq', num=isr_num - 16)
        else:
            isr_str = t('decode_psr_reserved')
        ret_val.append(t('decode_psr_exception', num=isr_num, name=isr_str))

        # Состояние Thumb
        thumb = (psr_value >> 24) & 1
        ret_val.append(t('decode_psr_thumb', val=thumb))
        if thumb == 0:
            ret_val.append(t('decode_psr_thumb_warn'))

        return ret_val

#===============================================================================
# Основная функция анализа
#===============================================================================

    def analyze_fault(self):
        """
        @brief  Main fault analysis entry point

        @details Performs the following steps:
                 1. Parse hex values from all input fields
                 2. Decode all fault status registers (CFSR, HFSR, DFSR, AFSR)
                 3. Decode PSR (Program Status Register)
                 4. Run fault diagnosis with remediation recommendations
                 5. Save the result to analysis history

                 Output is shown in two panels:
                 - Upper panel: decoded register bit-fields
                 - Lower panel: fault diagnosis with problem description
        """
        self.decode_text.delete(1.0, tk.END)
        self.results_text.delete(1.0, tk.END)

        # Автозагрузка MAP файла если путь задан, но символы ещё не загружены
        map_path = self.map_file_combo.get().strip()
        if map_path and not self.map_symbols and os.path.exists(map_path):
            self.load_map_file(map_path)

        # Парсинг значений из полей ввода
        registers = {}
        for reg_name, entry in self.reg_entries.items():
            registers[reg_name] = self.parse_hex_value(entry.get())

#-------------------------------------------------------------------------------
# ДЕКОДИРОВАНИЕ FAULT STATUS РЕГИСТРОВ
#-------------------------------------------------------------------------------

        # CFSR (Configurable Fault Status Register)
        cfsr_decoded = self.decode_cfsr(registers['CFSR'])
        for line in cfsr_decoded:
            if '[!]' in line:
                self.decode_text.insert(tk.END, line + '\n', 'error')
            elif '[OK]' in line:
                self.decode_text.insert(tk.END, line + '\n', 'ok')
            else:
                self.decode_text.insert(tk.END, line + '\n')

        self.decode_text.insert(tk.END, '\n')

        # HFSR
        hfsr_decoded = self.decode_hfsr(registers['HFSR'])
        for line in hfsr_decoded:
            if '[!]' in line:
                self.decode_text.insert(tk.END, line + '\n', 'error')
            elif '[OK]' in line:
                self.decode_text.insert(tk.END, line + '\n', 'ok')
            else:
                self.decode_text.insert(tk.END, line + '\n')

        self.decode_text.insert(tk.END, '\n')

        # DFSR
        dfsr_decoded = self.decode_dfsr(registers['DFSR'])
        for line in dfsr_decoded:
            if '[!]' in line:
                self.decode_text.insert(tk.END, line + '\n', 'warning')
            elif '[OK]' in line:
                self.decode_text.insert(tk.END, line + '\n', 'ok')
            else:
                self.decode_text.insert(tk.END, line + '\n')

        self.decode_text.insert(tk.END, '\n')

        # AFSR
        afsr_decoded = self.decode_afsr(registers['AFSR'])
        for line in afsr_decoded:
            if '[!]' in line:
                self.decode_text.insert(tk.END, line + '\n', 'error')
            elif '[OK]' in line:
                self.decode_text.insert(tk.END, line + '\n', 'ok')
            else:
                self.decode_text.insert(tk.END, line + '\n', 'info')

        self.decode_text.insert(tk.END, '\n')

        # PSR
        psr_decoded = self.decode_psr(registers['PSR'])
        for line in psr_decoded:
            if '[!]' in line or 'WARNING' in line:
                self.decode_text.insert(tk.END, line + '\n', 'warning')
            else:
                self.decode_text.insert(tk.END, line + '\n', 'info')

        # === ДИАГНОСТИКА ===
        diagnosis = self.diagnose_fault(registers)

        for severity, message in diagnosis:
            self.results_text.insert(tk.END, f"{message}\n", severity)

        # Сохранение в историю
        self.save_to_history(registers)

    def diagnose_fault(self, registers):
        """
        @brief  Diagnose fault cause and provide remediation recommendations

        @details Analyses bit-fields of fault registers and determines:
                 - Fault type (HardFault / MemManage / BusFault / UsageFault)
                 - Root cause of the fault
                 - Addresses of faulting instructions / data (PC, BFAR, MMFAR)
                 - Step-by-step remediation advice

        @param[in]  registers  Dictionary with all register values
        @return     List of (severity, message) tuples for display
                    severity: 'error', 'warning', 'info', 'ok'
        """
        ret_val = []

        cfsr = registers['CFSR']
        hfsr = registers['HFSR']
        pc = registers['PC']
        lr = registers['LR']

        ret_val.append(('info', t('diag_pc', pc=pc)))
        pc_func = self.resolve_pc_to_function(pc)
        if pc_func:
            ret_val.append(('info', t('diag_pc_func', name=pc_func)))
        ret_val.append(('info', t('diag_lr', lr=lr)))
        exc_return = self.decode_exc_return(lr)
        if exc_return:
            ret_val.append(('info', t('diag_lr_exc_return', desc=exc_return)))
        else:
            lr_func = self.resolve_pc_to_function(lr & ~1)  # сброс Thumb-бита
            if lr_func:
                ret_val.append(('info', t('diag_lr_called_from', name=lr_func)))
        ret_val.append(('info', ""))

#-------------------------------------------------------------------------------
# Анализ значений регистров R0-R3, R12, SP
#-------------------------------------------------------------------------------
        bfar_val    = registers['BFAR']
        mmfar_val   = registers['MMFAR']
        bfar_valid  = bool((cfsr >> 8) & (1 << 7))  # BFARVALID  (BFSR bit 7)
        mmfar_valid = bool(cfsr & (1 << 7))         # MMARVALID  (MMFSR bit 7)

        ret_val.append(('info', t('diag_regs_header')))
        for reg in ('R0', 'R1', 'R2', 'R3', 'R12'):
            val = registers[reg]
            notes = []
            notes.append(self.identify_memory_region(val))
            magic = self.identify_magic_value(val)
            if magic:
                notes.append(magic)
            if bfar_valid and val == bfar_val:
                notes.append(t('diag_bfar_match'))
            if mmfar_valid and val == mmfar_val:
                notes.append(t('diag_mmfar_match'))
            if not magic:
                sym = self.resolve_pc_to_function(val)
                if sym and (0x08000000 <= val <= 0x1FFFFFFF):
                    notes.append(f"~ {sym}")
            note_str = "  |  ".join(notes)
            sev = (
                'error' if (t('diag_bfar_match') in note_str or 
                            t('diag_mmfar_match') in note_str)
                else 'warning' if 'NULL' in note_str
                else 'info'
            )
            ret_val.append((sev, f"  {reg:<3} = 0x{val:08X}  \u2192 {note_str}"))

        # SP — отдельно, с проверкой выравнивания и диапазона
        sp = registers.get('SP', 0)
        sp_notes = [self.identify_memory_region(sp)]
        sp_sev = 'info'
        if sp & 3:
            sp_notes.append(t('diag_sp_not_aligned4'))
            sp_sev = 'error'
        elif sp & 7:
            sp_notes.append(t('diag_sp_not_aligned8'))
            sp_sev = 'warning'
        if not (0x20000000 <= sp <= 0x3FFFFFFF):
            sp_notes.append(t('diag_sp_out_of_sram'))
            sp_sev = 'error'
        ret_val.append((
            sp_sev,
            f"  SP  = 0x{sp:08X}  \u2192 {'  |  '.join(sp_notes)}"
        ))

        ret_val.append(('info', ""))

        # Извлечение битовых полей из CFSR
        mmfsr = cfsr & 0xFF           # [7:0]   MemManage Fault Status
        bfsr = (cfsr >> 8) & 0xFF     # [15:8]  BusFault Status
        ufsr = (cfsr >> 16) & 0xFFFF  # [31:16] UsageFault Status

        # Проверка HardFault escalation
        if hfsr & (1 << 30):
            ret_val.append(('error', t('diag_forced_hf')))
            ret_val.append(('warning', t('diag_forced_hf_sub')))
            ret_val.append(('info', t('diag_forced_hf_see')))

#-------------------------------------------------------------------------------
# Анализ MemManage Fault
#-------------------------------------------------------------------------------
        if mmfsr != 0:
            ret_val.append(('error', t('diag_mmfault_header')))

            if mmfsr & (1 << 0):  # IACCVIOL
                ret_val.append(('warning', t('diag_mm_iaccviol')))
                ret_val.append(('info', t('diag_mm_iaccviol_fix', pc=pc)))

            if mmfsr & (1 << 1):  # DACCVIOL
                ret_val.append(('warning', t('diag_mm_daccviol')))
                if mmfsr & (1 << 7):  # MMARVALID
                    ret_val.append((
                        'info',
                        t('diag_mm_daccviol_addr', addr=registers['MMFAR'])
                    ))
                ret_val.append(('info', t('diag_mm_daccviol_fix')))

            if mmfsr & ((1 << 3) | (1 << 4)):
                ret_val.append(('warning', t('diag_mm_stack')))
                ret_val.append(('info', t('diag_mm_stack_fix')))

#-------------------------------------------------------------------------------
# Анализ BusFault
#-------------------------------------------------------------------------------
        if bfsr != 0:
            ret_val.append(('error', t('diag_busfault_header')))

            if bfsr & (1 << 0):  # IBUSERR
                ret_val.append(('warning', t('diag_bf_ibuserr')))
                ret_val.append(('info', t('diag_bf_ibuserr_pc', pc=pc)))
                ret_val.append(('info', t('diag_bf_ibuserr_fix')))

            if bfsr & (1 << 1):  # PRECISERR
                ret_val.append(('warning', t('diag_bf_preciserr')))
                if bfsr & (1 << 7):  # BFARVALID
                    ret_val.append((
                        'info',
                        t('diag_bf_preciserr_addr', addr=registers['BFAR'])
                    ))
                ret_val.append(('info', t('diag_bf_preciserr_fix')))

            if bfsr & (1 << 2):  # IMPRECISERR
                ret_val.append(('warning', t('diag_bf_impreciserr')))
                ret_val.append(('info', t('diag_bf_impreciserr_fix')))

            if bfsr & ((1 << 3) | (1 << 4)):  # UNSTKERR | STKERR
                ret_val.append(('warning', t('diag_bf_stack')))
                ret_val.append(('info', t('diag_bf_stack_fix')))

#-------------------------------------------------------------------------------
# Анализ UsageFault
#-------------------------------------------------------------------------------
        if ufsr != 0:
            ret_val.append(('error', t('diag_usagefault_header')))

            if ufsr & (1 << 0):  # UNDEFINSTR
                ret_val.append(('warning', t('diag_uf_undefinstr')))
                ret_val.append(('info', t('diag_uf_undefinstr_pc', pc=pc)))
                ret_val.append(('info', t('diag_uf_undefinstr_fix')))

            if ufsr & (1 << 1):
                ret_val.append(('warning', t('diag_uf_invstate')))
                ret_val.append(('info', t('diag_uf_invstate_fix')))

            if ufsr & (1 << 2):
                ret_val.append(('warning', t('diag_uf_invpc')))
                ret_val.append(('info', t('diag_uf_invpc_fix')))

            if ufsr & (1 << 8):
                ret_val.append(('warning', t('diag_uf_unaligned')))
                ret_val.append(('info', t('diag_uf_unaligned_fix')))

            if ufsr & (1 << 9):
                ret_val.append(('warning', t('diag_uf_divbyzero')))
                ret_val.append(('info', t('diag_uf_divbyzero_pc', pc=pc)))

        # Если нет fault флагов
        if cfsr == 0 and hfsr == 0:
            ret_val.append(('ok', t('diag_no_faults')))
            ret_val.append(('info', t('diag_no_faults_hint')))

        return ret_val

    def save_to_history(self, registers):
        """Append register snapshot to history list and persist it."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        history_entry = {
            'timestamp': timestamp,
            'registers': registers.copy(),
        }

        self.analysis_history.append(history_entry)
        self.history_listbox.insert(0, f"{timestamp} - PC=0x{registers['PC']:08X}")
        self._save_history()

    def on_history_select(self, event):
        """Handle item selection in the history list box."""
        selection = self.history_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        entry = self.analysis_history[len(self.analysis_history) - 1 - idx]

        self.history_text.delete(1.0, tk.END)

        # Показ деталей
        self.history_text.insert(
            tk.END,
            t('hist_analysis_from', ts=entry['timestamp']) + "\n\n",
            'info'
        )
        self.history_text.insert(tk.END, t('hist_registers') + "\n")
        for reg_name, value in entry['registers'].items():
            self.history_text.insert(tk.END, f"{reg_name}: 0x{value:08X}\n")

        self.history_text.tag_config('info', font=("Consolas", 9, "bold"))

    def restore_from_history(self):
        """Restore register values from the selected history entry."""
        selection = self.history_listbox.curselection()
        if not selection:
            messagebox.showwarning(t('msg_info'), t('msg_select_history'))
            return

        idx = selection[0]
        entry = self.analysis_history[len(self.analysis_history) - 1 - idx]

        # Восстановление значений в поля
        for reg_name, value in entry['registers'].items():
            self.reg_entries[reg_name].delete(0, tk.END)
            self.reg_entries[reg_name].insert(0, f"0x{value:08X}")

        # Переключение на вкладку анализа
        self.notebook.select(0)

        messagebox.showinfo(t('msg_success'), t('msg_restored'))

    def clear_history(self):
        """Clear all analysis history entries and erase the history file."""
        if messagebox.askyesno(t('dlg_confirm'), t('dlg_clear_hist_confirm')):
            self.analysis_history.clear()
            self.history_listbox.delete(0, tk.END)
            self.history_text.delete(1.0, tk.END)
            self._save_history()  # перезаписывает файл пустым списком []

    def clear_fields(self):
        """Reset all register input fields to their default values."""
        defaults = {'PSR': '0x01000000', 'SP': '0x20000000'}
        for reg_name, entry in self.reg_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, defaults.get(reg_name, '0x00000000'))

        self.decode_text.delete(1.0, tk.END)
        self.results_text.delete(1.0, tk.END)

    def load_from_file(self):
        """
        Open a file dialog and load a register dump from a JSON or text file.
        """
        initial_dir = self.settings.get('default_load_path', '')
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        filename = filedialog.askopenfilename(
            title=t('dlg_open_dump'),
            initialdir=initial_dir,
            filetypes=[
                ("JSON files", "*.json"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if not filename:
            return

        return self._load_json_file(filename)

    def save_results(self):
        """Export the current analysis results to a text file."""
        initial_dir = self.settings.get('default_save_path', '')
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        filename = filedialog.asksaveasfilename(
            title=t('dlg_save_results'),
            initialdir=initial_dir,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not filename:
            return

        ret_val = None
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(t('report_header') + "\n")
                f.write(t(
                    'report_timestamp',
                    ts=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ) + "\n\n")

                f.write(t('report_registers') + "\n")
                for reg_name, entry in self.reg_entries.items():
                    f.write(f"{reg_name}: {entry.get()}\n")

                f.write("\n" + t('report_decoded') + "\n")
                f.write(self.decode_text.get(1.0, tk.END))

                f.write("\n" + t('report_diagnosis') + "\n")
                f.write(self.results_text.get(1.0, tk.END))

            messagebox.showinfo(t('msg_success'), t('msg_results_saved'))
            ret_val = True
        except Exception as e:
            messagebox.showerror(t('msg_error'), t('msg_results_error', error=e))
            ret_val = False

        return ret_val

    def copy_diagnosis(self):
        """Copy the diagnosis text to the system clipboard."""
        text = self.results_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def show_recent_json_menu(self):
        """Display a popup menu with recently used JSON dump files."""
        recent = self.settings.get('recent_json_files', [])
        if not recent:
            messagebox.showinfo(t('msg_info'), t('msg_no_recent'))
            return
        menu = tk.Menu(self.root, tearoff=0)
        for path in recent:
            menu.add_command(
                label=os.path.basename(path),
                command=lambda p=path: self._load_json_file(p)
            )
        btn = self.recent_json_btn
        menu.post(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

    def _load_json_file(self, filename):
        """
        @brief  Load a JSON fault dump from the specified file path

        @param[in]  filename  Absolute path to the JSON file
        @return     True on success, False on failure
        """
        ret_val = None
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            for reg_name, value in data.items():
                if reg_name in self.reg_entries:
                    self.reg_entries[reg_name].delete(0, tk.END)
                    if isinstance(value, int):
                        self.reg_entries[reg_name].insert(0, f"0x{value:08X}")
                    else:
                        self.reg_entries[reg_name].insert(0, str(value))
            self._add_to_recent_json(filename)
            messagebox.showinfo(t('msg_success'), t('msg_dump_loaded'))
            ret_val = True
        except Exception as e:
            messagebox.showerror(t('msg_error'), t('msg_dump_error', error=e))
            ret_val = False
        return ret_val

    def _add_to_recent_map(self, path):
        """
        @brief  Add a MAP file path to the recent files list
                and update the Combobox

        @param[in]  path  Absolute path to the MAP file
        """
        recent = self.settings.setdefault('recent_map_files', [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        lim = self.settings.get('recent_files_limit', 5)
        self.settings['recent_map_files'] = recent[:lim]
        self.map_file_combo['values'] = self.settings['recent_map_files']
        self._autosave_settings()

    def _add_to_recent_json(self, path):
        """
        @brief  Add a JSON dump file path to the recent files list

        @param[in]  path  Absolute path to the JSON dump file
        """
        recent = self.settings.setdefault('recent_json_files', [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        lim = self.settings.get('recent_files_limit', 5)
        self.settings['recent_json_files'] = recent[:lim]
        self._autosave_settings()

    def _autosave_settings(self):
        """
        @brief  Silently save settings (including recent file lists)
                to config file
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception:
            pass

    def _save_history(self):
        """
        @brief  Persist analysis history to a JSON file (last 50 entries)
        """
        try:
            lim = int(self.settings.get('history_limit', 50))
            data = self.analysis_history[-lim:]
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_history(self):
        """
        @brief  Load analysis history from JSON file on startup
        """
        try:
            if not os.path.exists(self.history_file):
                return
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for entry in data:
                self.analysis_history.append(entry)
                ts = entry.get('timestamp', '?')
                pc = entry.get('registers', {}).get('PC', 0)
                self.history_listbox.insert(0, f"{ts} - PC=0x{pc:08X}")
        except Exception:
            pass

################################################################################
#                              Точка входа                                     #
################################################################################

def main():
    """
    @brief  Application entry point.

    @details Creates the Tkinter root window, instantiates ARMFaultAnalyzer
             and starts the GUI event loop.
    """
    if not validate_py_version():
        sys.exit(1)
    root = tk.Tk()
    app = ARMFaultAnalyzer(root)
    root.mainloop()

if __name__ == "__main__":
    main()

################################################################################
#                       Конец файла arm_fault_analyzer.py                      #
################################################################################
