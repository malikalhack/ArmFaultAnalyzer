#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 *******************************************************************************
 * @file    arm_fault_analyzer.py
 * @version 0.4.0
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
import sys
import os
from datetime import datetime

################################################################################
#                              Версия приложения                               #
################################################################################

APP_VERSION = "0.5.0"

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
#                        Класс ARM Fault Analyzer                              #
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

    def __init__(self, root):
        """
        @brief  Initialize the main application window

        @param[in]  root  Tkinter root window object
        """
        self.root = root
        self.root.title("ARM Cortex-M Fault Analyzer")
        self.root.geometry("1100x870")

        # Настройки по умолчанию
        self.config_file = "arm_analyzer_config.json"
        self.settings = {
            'default_load_path': '',
            'default_save_path': ''
        }
        self.load_settings()

        # Создание вкладок
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Вкладка анализа
        self.analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_frame, text="Анализ регистров")

        # Вкладка истории
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="История")

        # Вкладка настроек
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Настройки")

        # Вкладка помощи
        self.help_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.help_frame, text="Помощь")

        # Инициализация UI
        self.create_analysis_tab()
        self.create_history_tab()
        self.create_settings_tab()
        self.create_help_tab()

        # История анализов
        self.analysis_history = []
        self.map_symbols = []

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
        core_frame = ttk.LabelFrame(left_panel, text="Регистры процессора", padding=10)
        core_frame.pack(fill=tk.X, pady=5)

        self.reg_entries = {}
        core_regs = [
            ("R0", "0x00000000"),
            ("R1", "0x00000000"),
            ("R2", "0x00000000"),
            ("R3", "0x00000000"),
            ("R12", "0x00000000"),
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
        fault_frame = ttk.LabelFrame(left_panel, text="Fault Status Registers", padding=10)
        fault_frame.pack(fill=tk.X, pady=5)

        fault_regs = [
            ("CFSR", "0x00000000", "Configurable Fault Status"),
            ("HFSR", "0x00000000", "HardFault Status"),
            ("DFSR", "0x00000000", "Debug Fault Status"),
            ("AFSR", "0x00000000", "Auxiliary Fault Status"),
            ("BFAR", "0x00000000", "BusFault Address"),
            ("MMFAR", "0x00000000", "MemManage Fault Address"),
        ]

        for reg_name, default_val, tooltip in fault_regs:
            frame = ttk.Frame(fault_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=f"{reg_name}:", width=8).pack(side=tk.LEFT)
            entry = ttk.Entry(frame, width=18)
            entry.insert(0, default_val)
            entry.pack(side=tk.LEFT, padx=5)
            self.reg_entries[reg_name] = entry

            # Tooltip
            label = ttk.Label(frame, text="?", foreground="blue", cursor="hand2")
            label.pack(side=tk.LEFT)
            self.create_tooltip(label, tooltip)

        # Кнопки управления
        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(
            btn_frame,
            text="Анализировать",
            command=self.analyze_fault
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            btn_frame,
            text="Очистить",
            command=self.clear_fields
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            btn_frame,
            text="Загрузить из файла",
            command=self.load_from_file
        ).pack(fill=tk.X, pady=2)
        ttk.Button(
            btn_frame,
            text="Сохранить результат",
            command=self.save_results
        ).pack(fill=tk.X, pady=2)

        # === ПРАВАЯ ПАНЕЛЬ ===

        # Декодированные флаги
        decode_frame = ttk.LabelFrame(
            right_panel,
            text="Декодированные флаги",
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
            text="Диагностика",
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
            text="Детали анализа",
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
            text="Восстановить",
            command=self.restore_from_history
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            btn_frame,
            text="Очистить историю",
            command=self.clear_history
        ).pack(side=tk.LEFT, padx=2)

    def create_settings_tab(self):
        """Create the settings tab."""

        main_frame = ttk.Frame(self.settings_frame, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        title_label = ttk.Label(
            main_frame,
            text="Настройки приложения",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Пути по умолчанию
        paths_frame = ttk.LabelFrame(
            main_frame,
            text="Пути по умолчанию",
            padding=15
        )
        paths_frame.pack(fill=tk.X, pady=10)

        # Путь для загрузки
        load_frame = ttk.Frame(paths_frame)
        load_frame.pack(fill=tk.X, pady=5)
        ttk.Label(
            load_frame,
            text="Каталог загрузки дампов:",
            width=28
        ).pack(side=tk.LEFT)
        self.load_path_entry = ttk.Entry(load_frame, width=40)
        self.load_path_entry.pack(side=tk.LEFT, padx=5)
        self.load_path_entry.insert(0, self.settings['default_load_path'])
        ttk.Button(
            load_frame,
            text="Обзор...",
            command=lambda: self.browse_directory(self.load_path_entry)
        ).pack(side=tk.LEFT)

        # Путь для сохранения
        save_frame = ttk.Frame(paths_frame)
        save_frame.pack(fill=tk.X, pady=5)
        ttk.Label(
            save_frame,
            text="Каталог сохранения отчётов:",
            width=28
        ).pack(side=tk.LEFT)
        self.save_path_entry = ttk.Entry(save_frame, width=40)
        self.save_path_entry.pack(side=tk.LEFT, padx=5)
        self.save_path_entry.insert(0, self.settings['default_save_path'])
        ttk.Button(
            save_frame,
            text="Обзор...",
            command=lambda: self.browse_directory(self.save_path_entry)
        ).pack(side=tk.LEFT)

        # Кнопки управления
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(
            btn_frame,
            text="Сохранить настройки",
            command=self.save_settings_ui
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame,
            text="Сбросить по умолчанию",
            command=self.reset_settings
        ).pack(side=tk.LEFT, padx=5)

        # Информация о конфигурационном файле
        info_frame = ttk.LabelFrame(main_frame, text="Информация", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(
            info_frame,
            text=f"Файл настроек: {os.path.abspath(self.config_file)}",
            font=("Consolas", 8),
            foreground="gray"
        ).pack(anchor=tk.W)
        ttk.Label(
            info_frame,
            text="Если пути не заданы — используются стандартные диалоги открытия/сохранения.",
            font=("Arial", 9),
            foreground="gray"
        ).pack(anchor=tk.W, pady=(4, 0))

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

        help_content = """\
╔══════════════════════════════════════════════════════════════╗
║        ARM Cortex-M Fault Analyzer - Руководство             ║
╚══════════════════════════════════════════════════════════════╝

1. ОБЩЕЕ ОПИСАНИЕ
   ═══════════════════════════════════════════════════════════

   Инструмент предназначен для анализа системных ошибок (fault)
   на микроконтроллерах ARM Cortex-M (M0/M0+/M3/M4/M7).

   Поддерживаемые типы fault:
   • HardFault    - критическая ошибка
   • MemManage    - нарушение доступа к памяти (MPU)
   • BusFault     - ошибка шины (невалидный адрес)
   • UsageFault   - ошибка выполнения инструкции
   • Debug Fault  - отладочное событие

2. КАК ПОЛУЧИТЬ ЗНАЧЕНИЯ РЕГИСТРОВ
   ═══════════════════════════════════════════════════════════

   Используйте паттерн naked + C-handler в обработчиках ошибок:

   /* Trampoline macro - checks LR to select MSP or PSP */
   #define FAULT_TRAMPOLINE() \\
       __asm volatile( \\
           "tst  lr, #4              \\n" \\
           "ite  eq                  \\n" \\
           "mrseq r0, msp            \\n" /* fault in Thread mode, MSP */ \\
           "mrsne r0, psp            \\n" /* fault in Handler mode, PSP */ \\
           "b    Common_Fault_Handler_C \\n" \\
       )

   /* Naked handlers - no compiler prologue/epilogue, trampoline only */
   __attribute__((naked)) void HardFault_Handler(void)  { FAULT_TRAMPOLINE(); }
   __attribute__((naked)) void BusFault_Handler(void)   { FAULT_TRAMPOLINE(); }
   __attribute__((naked)) void MemManage_Handler(void)  { FAULT_TRAMPOLINE(); }

   /* C-level handler receives the stacked frame as fault_args[] */
   void Common_Fault_Handler_C(uint32_t *fault_args)
   {
       __disable_irq();

       /* Registers saved automatically onto the stack by the CPU */
       volatile uint32_t stacked_r0  = fault_args[0];
       volatile uint32_t stacked_r1  = fault_args[1];
       volatile uint32_t stacked_r2  = fault_args[2];
       volatile uint32_t stacked_r3  = fault_args[3];
       volatile uint32_t stacked_r12 = fault_args[4];
       volatile uint32_t stacked_lr  = fault_args[5];
       volatile uint32_t stacked_pc  = fault_args[6]; /* address of faulting instruction */
       volatile uint32_t stacked_psr = fault_args[7];

       /* Fault Status Registers (read before they are cleared) */
       volatile uint32_t cfsr = SCB->CFSR;  /* 0xE000ED28 - MMFSR/BFSR/UFSR combined */
       volatile uint32_t hfsr = SCB->HFSR;  /* 0xE000ED2C - bit30 FORCED = escalated  */
       volatile uint32_t dfsr = SCB->DFSR;  /* 0xE000ED30 - debug fault status         */
       volatile uint32_t afsr = SCB->AFSR;  /* 0xE000ED3C - implementation defined     */
       volatile uint32_t bfar = SCB->BFAR;  /* 0xE000ED38 - valid when BFARVALID=1     */
       volatile uint32_t mmar = SCB->MMFAR; /* 0xE000ED34 - valid when MMARVALID=1     */

       /* Suppress unused-variable warnings in release builds */
       (void)stacked_r0;  (void)stacked_r1;  (void)stacked_r2;  (void)stacked_r3;
       (void)stacked_r12; (void)stacked_lr;  (void)stacked_pc;  (void)stacked_psr;
       (void)cfsr; (void)hfsr; (void)dfsr; (void)afsr; (void)bfar; (void)mmar;
       /* Set a breakpoint here, then read the volatile vars in the debugger
          and paste the hex values into the ARM Fault Analyzer. */
       while (1);
   }

   ИЛИ используйте отладчик (GDB, J-Link, SEGGER):
   • Остановитесь на breakpoint в обработчике fault
   • Считайте регистры через Memory View или команды

3. ПОРЯДОК РАБОТЫ С АНАЛИЗАТОРОМ
   ═══════════════════════════════════════════════════════════

   Шаг 1: Ввод данных
   ──────────────────
   Введите значения регистров вручную в hex формате:
     R0-R3, R12, LR, PC, PSR   - регистры процессора
     CFSR, HFSR, DFSR, AFSR    - fault status регистры
     BFAR, MMFAR               - адреса ошибок

   Или загрузите из JSON файла ("Загрузить из файла").

   Шаг 2: Анализ
   ─────────────
   Нажмите кнопку "Анализировать".

   Результаты:
   • Правая верхняя панель - декодированные флаги регистров
   • Правая нижняя панель - диагностика с описанием проблемы

   Шаг 3: Интерпретация
   ────────────────────
   Диагностика покажет:
   • Тип fault (MemManage/BusFault/UsageFault/HardFault)
   • Причину возникновения
   • Рекомендации по устранению
   • Адреса проблемных инструкций/данных

4. ФОРМАТ JSON ДАМПА
   ═══════════════════════════════════════════════════════════

   Пример файла fault_dump.json:

   {
       "R0": "0x20000100",
       "R1": "0x00000000",
       "R2": "0x08001234",
       "R3": "0xDEADBEEF",
       "R12": "0x00000000",
       "LR": "0x08000401",
       "PC": "0x08002468",
       "PSR": "0x01000000",
       "CFSR": "0x00000082",
       "HFSR": "0x40000000",
       "DFSR": "0x00000000",
       "AFSR": "0x00000000",
       "BFAR": "0x20000100",
       "MMFAR": "0x00000000"
   }

5. РАСШИФРОВКА РЕГИСТРОВ
   ═══════════════════════════════════════════════════════════

   PC (Program Counter)
   ────────────────────
   Адрес инструкции, на которой произошла ошибка.
   Используйте .map файл для определения функции.

   LR (Link Register)
   ──────────────────
   Адрес возврата. Может указывать на вызывающую функцию.

   PSR (Program Status Register)
   ─────────────────────────────
   • Биты 31-28: флаги N, Z, C, V (арифметика)
   • Биты 8-0: номер текущего exception
   • Бит 24: Thumb bit (должен быть 1)

   CFSR (Configurable Fault Status Register)
   ─────────────────────────────────────────
   Объединяет три регистра:
   • MMFSR (биты 7-0)   - MemManage fault
   • BFSR  (биты 15-8)  - BusFault
   • UFSR  (биты 31-16) - UsageFault

   HFSR (HardFault Status Register)
   ────────────────────────────────
   • Бит 30: FORCED - эскалация из другого fault
   • Бит 1: VECTTBL - ошибка чтения таблицы векторов

   MMFAR / BFAR
   ────────────
   Содержат адрес памяти, вызвавший MemManage или BusFault.
   Валидны только если установлен флаг MMARVALID/BFARVALID.

6. ТИПОВЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ
   ═══════════════════════════════════════════════════════════

   Проблема: IBUSERR (Instruction bus error)
   ─────────────────────────────────────────
   Причина: PC указывает на невалидный адрес Flash памяти
   Решение:
   • Проверьте таблицу векторов прерываний
   • Убедитесь что PC в диапазоне Flash (0x08000000+)
   • Проверьте наличие повреждения Flash

   Проблема: PRECISERR (Precise data bus error)
   ────────────────────────────────────────────
   Причина: Обращение к невалидному адресу памяти
   Решение:
   • Проверьте адрес в BFAR
   • Проверьте указатели на NULL
   • Проверьте выход за границы массива
   • Проверьте адреса периферии

   Проблема: UNDEFINSTR (Undefined instruction)
   ────────────────────────────────────────────
   Причина: Попытка выполнить неизвестную инструкцию
   Решение:
   • Проверьте содержимое по адресу PC в дизассемблере
   • Возможно повреждение Flash или ошибочный переход

   Проблема: UNALIGNED (Unaligned access)
   ──────────────────────────────────────
   Причина: Невыровненный доступ к памяти
   Решение:
   • Используйте __attribute__((packed)) или __packed
   • Убедитесь что структуры выровнены правильно
   • Проверьте приведение типов указателей

   Проблема: DIVBYZERO (Division by zero)
   ───────────────────────────────────────
   Причина: Деление на ноль (требует включения trap)
   Решение:
   • Найдите код деления в районе адреса PC
   • Добавьте проверку делителя перед делением

   Проблема: MSTKERR/MUNSTKERR (Stack error)
   ─────────────────────────────────────────
   Причина: Переполнение стека или MPU защита
   Решение:
   • Увеличьте размер стека в linker script
   • Проверьте рекурсивные вызовы
   • Проверьте большие локальные переменные
   • Проверьте настройки MPU

7. ДОПОЛНИТЕЛЬНЫЕ ВОЗМОЖНОСТИ
   ═══════════════════════════════════════════════════════════

   История анализов
   ────────────────
   Все выполненные анализы сохраняются во вкладке "История".
   Можно восстановить значения из предыдущего анализа.

   Экспорт результатов
   ───────────────────
   Кнопка "Сохранить результат" - экспорт полного отчёта
   в текстовый файл для документации или отправки коллегам.

   Настройки путей
   ───────────────
   Вкладка "Настройки" позволяет задать пути по умолчанию
   для загрузки дампов и сохранения отчётов.

8. ПОЛЕЗНЫЕ ССЫЛКИ
   ═══════════════════════════════════════════════════════════

   • ARM Cortex-M Programming Guide:
     https://developer.arm.com/documentation/

   • Exception and Fault Handling:
     ARM DDI 0403E (ARMv7-M Architecture Reference Manual)

   • Fault Status Registers:
     https://developer.arm.com/documentation/100165/

9. СОВЕТЫ ПО ОТЛАДКЕ
   ═══════════════════════════════════════════════════════════

   1. Всегда проверяйте PC - это адрес проблемной инструкции

   2. Используйте .map файл или objdump для определения функции:
      arm-none-eabi-objdump -d firmware.elf | grep <PC_address>

   3. При FORCED HardFault смотрите CFSR - там реальная причина

   4. BFAR и MMFAR валидны только если установлены флаги
      BFARVALID и MMARVALID соответственно

   5. Включите UsageFault, BusFault, MemManage в SCB->SHCSR:
      SCB->SHCSR |= (SCB_SHCSR_USGFAULTENA_Msk |
                     SCB_SHCSR_BUSFAULTENA_Msk |
                     SCB_SHCSR_MEMFAULTENA_Msk);

   6. Для более точной диагностики BusFault используйте
      precise mode (отключите write buffering если нужно)

══════════════════════════════════════════════════════════════
                    (C) 2026 ARM Fault Analyzer
══════════════════════════════════════════════════════════════
"""
        help_text.insert(1.0, help_content)
        help_text.config(state=tk.DISABLED)  # Только чтение

        # Настройка цветовых тегов
        help_text.tag_config("header", font=("Consolas", 11, "bold"))

    def browse_directory(self, entry_widget):
        """Выбор каталога"""
        directory = filedialog.askdirectory(
            title="Выберите каталог",
            initialdir=entry_widget.get() if entry_widget.get() else os.getcwd()
        )
        if directory:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, directory)

    def browse_map_file(self):
        """Выбор MAP файла через диалог и его немедленная загрузка"""
        initial_dir = self.settings.get('default_load_path', '')
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        filename = filedialog.askopenfilename(
            title="Открыть MAP файл",
            initialdir=initial_dir,
            filetypes=[("MAP files", "*.map"), ("All files", "*.*")]
        )
        if filename:
            self.map_file_entry.delete(0, tk.END)
            self.map_file_entry.insert(0, filename)
            self.load_map_file(filename)

    def clear_map_file(self):
        """Сброс загруженного MAP файла"""
        self.map_file_entry.delete(0, tk.END)
        self.map_symbols = []
        self.map_status_label.config(text="Файл не загружен", foreground="gray")

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
        """Read settings from the UI controls and save them to the config file."""
        self.settings['default_load_path'] = self.load_path_entry.get()
        self.settings['default_save_path'] = self.save_path_entry.get()

        ret_val = None
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            messagebox.showinfo("Успех", "Настройки сохранены")
            ret_val = True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки:\n{e}")
            ret_val = False
        return ret_val

    def reset_settings(self):
        """Reset all settings to their default values."""
        if messagebox.askyesno("Подтверждение", "Сбросить настройки по умолчанию?"):
            self.load_path_entry.delete(0, tk.END)
            self.save_path_entry.delete(0, tk.END)
            self.settings['default_load_path'] = ''
            self.settings['default_save_path'] = ''
            messagebox.showinfo("Готово", "Настройки сброшены")

    def create_tooltip(self, widget, text):
        """Attach a hover tooltip to a widget."""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = ttk.Label(tooltip, text=text, background="lightyellow", 
                            relief=tk.SOLID, borderwidth=1, padding=5)
            label.pack()
            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def parse_hex_value(self, value_str):
        """Parse a hex string (with or without '0x' prefix) and return an integer."""
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

    def resolve_pc_to_function(self, pc):
        """
        @brief  Find the function name for a given PC address via binary search

        @details Returns the name of the function whose start address is the
                 largest address that is <= pc (i.e., pc falls inside that function).

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
                 Code / SRAM / Peripheral / External RAM / External Device / System.
                 STM32-specific peripheral sub-ranges are also listed.

        @param[in]  addr  32-bit address to identify
        @return     Human-readable region string
        """
        # ARM Cortex-M generic zones
        REGIONS = [
            (0x00000000, 0x1FFFFFFF, "Code region (Flash/ROM)"),
            (0x20000000, 0x3FFFFFFF, "SRAM region"),
            (0x40000000, 0x4FFFFFFF, "Peripheral region"),
            (0x60000000, 0x9FFFFFFF, "External RAM region"),
            (0xA0000000, 0xDFFFFFFF, "External Device region"),
            (0xE0000000, 0xFFFFFFFF, "System region (SCS/DWT/ITM)"),
        ]
        # STM32 APB/AHB sub-zones (common across most families)
        STM32_ZONES = [
            (0x40000000, 0x40007FFF, "STM32 APB1"),
            (0x40010000, 0x40017FFF, "STM32 APB2"),
            (0x40020000, 0x4007FFFF, "STM32 AHB1 / APB3"),
            (0x50000000, 0x5FFFFFFF, "STM32 AHB2/3 (GPIO/USB/SDMMC)"),
            (0xE0001000, 0xE0001FFF, "DWT (Data Watchpoint)"),
            (0xE0002000, 0xE0002FFF, "FPB (Flash Patch)"),
            (0xE000E000, 0xE000EFFF, "SCS (NVIC/SCB/SysTick)"),
            (0xE0040000, 0xE00FFFFF, "TPIU/ETM/CoreSight"),
        ]
        ret_val = "Unknown region"
        # Check STM32 sub-zones first (more specific)
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

#-------------------------------------------------------------------------------
# Decode Functions - Fault Status Registers
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
        ret_val.append("=== MMFSR (MemManage Fault) ===")

        if mmfsr & (1 << 0):
            ret_val.append("  [!] IACCVIOL: Instruction access violation")
        if mmfsr & (1 << 1):
            ret_val.append("  [!] DACCVIOL: Data access violation")
        if mmfsr & (1 << 3):
            ret_val.append("  [!] MUNSTKERR: MemManage fault on unstacking")
        if mmfsr & (1 << 4):
            ret_val.append("  [!] MSTKERR: MemManage fault on stacking")
        if mmfsr & (1 << 5):
            ret_val.append("  [!] MLSPERR: MemManage fault during FP lazy state preservation")
        if mmfsr & (1 << 7):
            ret_val.append("  [!] MMARVALID: MMFAR contains valid address")

        if mmfsr == 0:
            ret_val.append("  [OK] No MemManage faults")

        # BFSR (bits 8-15) - BusFault Status Register
        bfsr = (cfsr_value >> 8) & 0xFF
        ret_val.append("\n=== BFSR (BusFault) ===")

        if bfsr & (1 << 0):
            ret_val.append("  [!] IBUSERR: Instruction bus error")
        if bfsr & (1 << 1):
            ret_val.append("  [!] PRECISERR: Precise data bus error")
        if bfsr & (1 << 2):
            ret_val.append("  [!] IMPRECISERR: Imprecise data bus error")
        if bfsr & (1 << 3):
            ret_val.append("  [!] UNSTKERR: BusFault on unstacking")
        if bfsr & (1 << 4):
            ret_val.append("  [!] STKERR: BusFault on stacking")
        if bfsr & (1 << 5):
            ret_val.append("  [!] LSPERR: BusFault during FP lazy state preservation")
        if bfsr & (1 << 7):
            ret_val.append("  [!] BFARVALID: BFAR contains valid address")

        if bfsr == 0:
            ret_val.append("  [OK] No BusFaults")

        # UFSR (bits 16-31) - UsageFault Status Register
        ufsr = (cfsr_value >> 16) & 0xFFFF
        ret_val.append("\n=== UFSR (UsageFault) ===")

        if ufsr & (1 << 0):
            ret_val.append("  [!] UNDEFINSTR: Undefined instruction")
        if ufsr & (1 << 1):
            ret_val.append("  [!] INVSTATE: Invalid state (e.g., Thumb bit not set)")
        if ufsr & (1 << 2):
            ret_val.append("  [!] INVPC: Invalid PC load")
        if ufsr & (1 << 3):
            ret_val.append("  [!] NOCP: No coprocessor")
        if ufsr & (1 << 8):
            ret_val.append("  [!] UNALIGNED: Unaligned access")
        if ufsr & (1 << 9):
            ret_val.append("  [!] DIVBYZERO: Division by zero")

        if ufsr == 0:
            ret_val.append("  [OK] No UsageFaults")

        return ret_val

#-------------------------------------------------------------------------------

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
        ret_val.append("=== HFSR (HardFault Status) ===")

        if hfsr_value & (1 << 1):
            ret_val.append("  [!] VECTTBL: BusFault on vector table read")
        if hfsr_value & (1 << 30):
            ret_val.append("  [!] FORCED: Forced HardFault (escalated from other fault)")
        if hfsr_value & (1 << 31):
            ret_val.append("  [!] DEBUGEVT: Debug event")

        if hfsr_value == 0:
            ret_val.append("  [OK] No HardFault")

        return ret_val

#-------------------------------------------------------------------------------

    def decode_dfsr(self, dfsr_value):
        """
        @brief  Decode DFSR register (Debug Fault Status Register)

        @details Contains debug event status flags:
                 - HALTED, BKPT, DWTTRAP, VCATCH, EXTERNAL

        @param[in]  dfsr_value  DFSR register value (32-bit)
        @return     List of strings with decoded fault flags
        """
        ret_val = []
        ret_val.append("=== DFSR (Debug Fault Status) ===")

        if dfsr_value & (1 << 0):
            ret_val.append("  [!] HALTED: Halt request")
        if dfsr_value & (1 << 1):
            ret_val.append("  [!] BKPT: Breakpoint")
        if dfsr_value & (1 << 2):
            ret_val.append("  [!] DWTTRAP: DWT match")
        if dfsr_value & (1 << 3):
            ret_val.append("  [!] VCATCH: Vector catch triggered")
        if dfsr_value & (1 << 4):
            ret_val.append("  [!] EXTERNAL: External debug request")

        if dfsr_value == 0:
            ret_val.append("  [OK] No debug faults")

        return ret_val

#-------------------------------------------------------------------------------

    def decode_afsr(self, afsr_value):
        """
        @brief  Decode AFSR register (Auxiliary Fault Status Register)

        @details Implementation-defined register.
                 Interpretation depends on the MCU vendor (ST, NXP, TI, etc.)

        @param[in]  afsr_value  AFSR register value (32-bit)
        @return     List of strings with decoded fault flags
        """
        ret_val = []
        ret_val.append("=== AFSR (Auxiliary Fault Status) ===")

        if afsr_value == 0:
            ret_val.append("  [OK] No auxiliary faults")
        else:
            ret_val.append(f"  Implementation defined value: 0x{afsr_value:08X}")
            ret_val.append("  [INFO] Interpretation depends on MCU vendor")

        return ret_val

#-------------------------------------------------------------------------------

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
        ret_val.append("=== PSR (Program Status Register) ===")

        # APSR флаги
        ret_val.append("  APSR flags:")
        ret_val.append(f"    N (Negative): {(psr_value >> 31) & 1}")
        ret_val.append(f"    Z (Zero): {(psr_value >> 30) & 1}")
        ret_val.append(f"    C (Carry): {(psr_value >> 29) & 1}")
        ret_val.append(f"    V (Overflow): {(psr_value >> 28) & 1}")
        ret_val.append(f"    Q (Saturation): {(psr_value >> 27) & 1}")

        # ISR number
        isr_num = psr_value & 0x1FF
        ret_val.append(f"  Exception number: {isr_num}")

        # Thumb state
        thumb = (psr_value >> 24) & 1
        ret_val.append(f"  T (Thumb state): {thumb}")
        if thumb == 0:
            ret_val.append("    [!] WARNING: Thumb bit not set!")

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
        self.save_to_history(
            registers,
            cfsr_decoded,
            hfsr_decoded,
            dfsr_decoded,
            afsr_decoded,
            psr_decoded,
            diagnosis
        )

#-------------------------------------------------------------------------------

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

        ret_val.append(('info', f"PC (адрес ошибки): 0x{pc:08X}"))
        pc_func = self.resolve_pc_to_function(pc)
        if pc_func:
            ret_val.append((
                'info',
                f"  \u2192 \u0424\u0443\u043d\u043a\u0446\u0438\u044f: {pc_func}"
            ))
        ret_val.append(('info', f"LR (return address): 0x{lr:08X}"))
        lr_func = self.resolve_pc_to_function(lr & ~1)  # clear Thumb bit
        if lr_func:
            ret_val.append((
                'info',
                f"  \u2192 \u0412\u044b\u0437\u0432\u0430\u043d\u0430 \u0438\u0437: {lr_func}"
            ))
        ret_val.append(('info', ""))

#----------------------------------------------------------------------
# Анализ значений регистров R0-R3, R12
#----------------------------------------------------------------------
        bfar_val    = registers['BFAR']
        mmfar_val   = registers['MMFAR']
        bfar_valid  = bool((cfsr >> 8) & (1 << 7))  # BFARVALID  (BFSR bit 7)
        mmfar_valid = bool(cfsr & (1 << 7))          # MMARVALID  (MMFSR bit 7)

        ret_val.append(('info', "=== Анализ регистров R0-R3, R12 ==="))
        for reg in ('R0', 'R1', 'R2', 'R3', 'R12'):
            val = registers[reg]
            notes = []
            notes.append(self.identify_memory_region(val))
            magic = self.identify_magic_value(val)
            if magic:
                notes.append(magic)
            if bfar_valid and val == bfar_val:
                notes.append("← совпадает с BFAR (адрес нарушения шины!)")
            if mmfar_valid and val == mmfar_val:
                notes.append("← совпадает с MMFAR (адрес нарушения MPU!)")
            sym = self.resolve_pc_to_function(val)
            if sym and (0x08000000 <= val <= 0x1FFFFFFF):
                notes.append(f"~ {sym}")
            note_str = "  |  ".join(notes)
            sev = 'error'   if ('BFAR' in note_str or 'MMFAR' in note_str) else \
                  'warning' if 'NULL' in note_str else 'info'
            ret_val.append((sev, f"  {reg:<3} = 0x{val:08X}  → {note_str}"))

        ret_val.append(('info', ""))

        # Извлечение битовых полей из CFSR
        mmfsr = cfsr & 0xFF           # [7:0]   MemManage Fault Status
        bfsr = (cfsr >> 8) & 0xFF     # [15:8]  BusFault Status
        ufsr = (cfsr >> 16) & 0xFFFF  # [31:16] UsageFault Status

        # Проверка HardFault escalation
        if hfsr & (1 << 30):
            ret_val.append(('error', "КРИТИЧНО: Forced HardFault"))
            ret_val.append(('warning', "  → HardFault возник из-за эскалации другого fault"))
            ret_val.append(('info', "  → Причина указана в разделе MemManage/BusFault/UsageFault ниже"))

#-------------------------------------------------------------------------------
# MemManage Fault Analysis
#-------------------------------------------------------------------------------
        if mmfsr != 0:
            ret_val.append(('error', "\n[MemManage Fault обнаружен]"))

            if mmfsr & (1 << 0):  # IACCVIOL
                ret_val.append(('warning', "  Причина: Попытка выполнить код из защищенной области памяти"))
                ret_val.append(('info', f"  Решение: Проверьте MPU конфигурацию и адрес PC=0x{pc:08X}"))

            if mmfsr & (1 << 1):  # DACCVIOL
                ret_val.append(('warning', "  Причина: Попытка доступа к данным в защищенной области"))
                if mmfsr & (1 << 7):  # MMARVALID
                    ret_val.append(('info', f"  Адрес нарушения: 0x{registers['MMFAR']:08X} (см. MMFAR)"))
                ret_val.append(('info', "  Решение: Проверьте настройки MPU и указатели"))

            if mmfsr & ((1 << 3) | (1 << 4)):
                ret_val.append(('warning', "  Причина: Ошибка при stacking/unstacking (переполнение стека?)"))
                ret_val.append(('info', "  Решение: Увеличьте размер стека или проверьте рекурсию"))

#-------------------------------------------------------------------------------
# BusFault Analysis
#-------------------------------------------------------------------------------
        if bfsr != 0:
            ret_val.append(('error', "\n[BusFault обнаружен]"))

            if bfsr & (1 << 0):  # IBUSERR
                ret_val.append((
                    'warning',
                    "  Причина: Попытка чтения инструкции из недоступного адреса"
                ))
                ret_val.append(('info', f"  PC указывает на: 0x{pc:08X}"))
                ret_val.append((
                    'info',
                    "  Решение: Проверьте, что PC указывает на валидную Flash память"
                ))

            if bfsr & (1 << 1):  # PRECISERR
                ret_val.append((
                    'warning',
                    "  Причина: Precise data bus error - доступ к невалидному адресу"
                ))
                if bfsr & (1 << 7):  # BFARVALID
                    ret_val.append((
                        'info',
                        f"  Адрес нарушения: 0x{registers['BFAR']:08X} (см. BFAR)"
                    ))
                ret_val.append((
                    'info',
                    "  Решение: Проверьте указатели, периферию, выравнивание"
                ))

            if bfsr & (1 << 2):  # IMPRECISERR
                ret_val.append((
                    'warning',
                    "  Причина: Imprecise data bus error"
                ))
                ret_val.append((
                    'info',
                    "  Решение: Включите debug режим для точной диагностики"
                ))

            if bfsr & ((1 << 3) | (1 << 4)):  # UNSTKERR | STKERR
                ret_val.append((
                    'warning',
                    "  Причина: Ошибка bus при работе со стеком"
                ))
                ret_val.append((
                    'info',
                    "  Решение: Проверьте указатель стека (SP) и размер RAM"
                ))

#-------------------------------------------------------------------------------
# UsageFault Analysis
#-------------------------------------------------------------------------------
        if ufsr != 0:
            ret_val.append(('error', "\n[UsageFault обнаружен]"))

            if ufsr & (1 << 0):  # UNDEFINSTR
                ret_val.append((
                    'warning',
                    "  Причина: Попытка выполнить неопределенную инструкцию"
                ))
                ret_val.append((
                    'info',
                    f"  PC (адрес инструкции): 0x{pc:08X}"
                ))
                ret_val.append((
                    'info',
                    "  Решение: Проверьте содержимое по адресу PC в дизассемблере"
                ))

            if ufsr & (1 << 1):
                ret_val.append((
                    'warning',
                    "  Причина: Невалидное состояние процессора (Thumb bit?)"
                ))
                ret_val.append((
                    'info',
                    "  Решение: Убедитесь что все адреса функций имеют младший бит=1"
                ))

            if ufsr & (1 << 2):
                ret_val.append((
                    'warning',
                    "  Причина: Попытка загрузить невалидный PC"
                ))
                ret_val.append((
                    'info',
                    "  Решение: Проверьте таблицу векторов прерываний"
                ))

            if ufsr & (1 << 8):
                ret_val.append((
                    'warning',
                    "  Причина: Невыровненный доступ к памяти"
                ))
                ret_val.append((
                    'info',
                    "  Решение: Используйте выровненные структуры или packed атрибут"
                ))

            if ufsr & (1 << 9):
                ret_val.append(('warning', "  Причина: Деление на ноль"))
                ret_val.append((
                    'info',
                    f"  Проверьте код в районе PC=0x{pc:08X}"
                ))

        # Если нет fault флагов
        if cfsr == 0 and hfsr == 0:
            ret_val.append(('ok', "Fault flags не установлены"))
            ret_val.append((
                'info',
                "Возможно, это не fault или регистры уже сброшены"
            ))

        return ret_val

    def save_to_history(
        self, registers, decoded_cfsr, decoded_hfsr,
        decoded_dfsr, decoded_afsr, decoded_psr, diagnosis
    ):
        """Append the current analysis result to the history list and persist it."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        history_entry = {
            'timestamp': timestamp,
            'registers': registers.copy(),
            'cfsr_decoded': decoded_cfsr,
            'hfsr_decoded': decoded_hfsr,
            'dfsr_decoded': decoded_dfsr,
            'afsr_decoded': decoded_afsr,
            'psr_decoded': decoded_psr,
            'diagnosis': diagnosis
        }

        self.analysis_history.append(history_entry)
        self.history_listbox.insert(0, f"{timestamp} - PC=0x{registers['PC']:08X}")

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
            f"Анализ от: {entry['timestamp']}\n\n",
            'info'
        )
        self.history_text.insert(tk.END, "=== Регистры ===\n")
        for reg_name, value in entry['registers'].items():
            self.history_text.insert(tk.END, f"{reg_name}: 0x{value:08X}\n")

        self.history_text.tag_config('info', font=("Consolas", 9, "bold"))

    def restore_from_history(self):
        """Restore register values from the selected history entry."""
        selection = self.history_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите запись из истории")
            return

        idx = selection[0]
        entry = self.analysis_history[len(self.analysis_history) - 1 - idx]

        # Восстановление значений в поля
        for reg_name, value in entry['registers'].items():
            self.reg_entries[reg_name].delete(0, tk.END)
            self.reg_entries[reg_name].insert(0, f"0x{value:08X}")

        # Переключение на вкладку анализа
        self.notebook.select(0)

        messagebox.showinfo("Готово", "Значения восстановлены из истории")

    def clear_history(self):
        """Clear all analysis history entries."""
        if messagebox.askyesno("Подтверждение", "Очистить всю историю?"):
            self.analysis_history.clear()
            self.history_listbox.delete(0, tk.END)
            self.history_text.delete(1.0, tk.END)

    def clear_fields(self):
        """Reset all register input fields to their default values."""
        defaults = {'PSR': '0x01000000'}
        for reg_name, entry in self.reg_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, defaults.get(reg_name, '0x00000000'))

        self.decode_text.delete(1.0, tk.END)
        self.results_text.delete(1.0, tk.END)

    def load_from_file(self):
        """Open a file dialog and load a register dump from a JSON or text file."""
        initial_dir = self.settings.get('default_load_path', '')
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        filename = filedialog.askopenfilename(
            title="Открыть дамп регистров",
            initialdir=initial_dir,
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not filename:
            return

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

            messagebox.showinfo("Успех", "Дамп загружен из файла")
            ret_val = True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{e}")
            ret_val = False

        return ret_val

    def save_results(self):
        """Export the current analysis results to a text file."""
        initial_dir = self.settings.get('default_save_path', '')
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        filename = filedialog.asksaveasfilename(
            title="Сохранить результаты",
            initialdir=initial_dir,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not filename:
            return

        ret_val = None
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=== ARM Cortex-M Fault Analysis ===\n")
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                f.write("=== Регистры ===\n")
                for reg_name, entry in self.reg_entries.items():
                    f.write(f"{reg_name}: {entry.get()}\n")

                f.write("\n=== Декодированные флаги ===\n")
                f.write(self.decode_text.get(1.0, tk.END))

                f.write("\n=== Диагностика ===\n")
                f.write(self.results_text.get(1.0, tk.END))

            messagebox.showinfo("Успех", "Результаты сохранены")
            ret_val = True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")
            ret_val = False

        return ret_val

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
