#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 ******************************************************************************
 * @file    arm_fault_analyzer.py
 * @version 0.2.0
 * @author  Anton Chernov
 * @date    04/23/2026
 * @brief   ARM Cortex-M Fault Analyzer with GUI
 ******************************************************************************
"""

################################ Импорт модулей ################################
import tkinter as tk
import sys

################################################################################
#                              Версия приложения                               #
################################################################################

APP_VERSION = "0.2.0"

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
#                        Класс ARM Fault Analyzer                             #
################################################################################

class ARMFaultAnalyzer:
    """
    @brief  Main GUI class for the ARM Cortex-M fault register analyzer
    """
    
    def __init__(self, root):
        """
        @brief  Initialize the main application window
        
        @param[in]  root  Tkinter root window object
        """
        self.root = root
        self.root.geometry("1100x870")

################################################################################
#                              Точка входа                                     #
################################################################################

def main():
    """
    @brief  Application entry point.
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
