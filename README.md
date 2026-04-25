# ARM Cortex-M Fault Analyzer

A GUI tool for analyzing fault exceptions on ARM Cortex-M microcontrollers.

## Requirements

- Python 3.8+
- Standard library only (tkinter, json, os, sys, re, subprocess, datetime) - no third-party dependencies

## Usage

```bash
python arm_fault_analyzer.py
```

## Features

- Manual register input or loading from a JSON dump file
- MAP file support for two formats: **AC6 armlink** and **GNU LD** (auto-detected)
- PC / LR address resolution to function names via MAP file
- Register decoding: CFSR (MMFSR / BFSR / UFSR), HFSR, DFSR, AFSR, PSR
- ISR number decoding in PSR and EXC\_RETURN decoding in LR
- Analysis of R0–R3, R12, SP: memory region, magic value detection, BFAR/MMFAR match
- Persistent analysis history across sessions
- Report export to a text file
- One-click copy of diagnostics to clipboard

## JSON Dump Format

```json
{
    "R0":    "0x20000100",
    "R1":    "0x00000000",
    "R2":    "0x08001234",
    "R3":    "0xDEADBEEF",
    "R12":   "0x00000000",
    "SP":    "0x20004FF0",
    "LR":    "0x08000401",
    "PC":    "0x08002468",
    "PSR":   "0x01000000",
    "CFSR":  "0x00000082",
    "HFSR":  "0x40000000",
    "DFSR":  "0x00000000",
    "AFSR":  "0x00000000",
    "BFAR":  "0x20000100",
    "MMFAR": "0x00000000"
}
```

Not all fields are required - missing registers default to `0x00000000`.

## Data Files

| File | Contents |
|------|----------|
| `arm_analyzer_config.json` | Application settings, paths, recent file lists, language |
| `arm_analyzer_history.json` | Analysis history (up to N entries, configurable) |

## Settings

The **Settings** tab allows you to configure:

- Default directory for loading JSON dumps
- Default directory for saving reports
- Recent files list size (MAP and JSON)

Full usage guide, register descriptions, and common fault scenarios are available in the **Help** tab inside the application.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | April 2026 | Added history saving for JSON and MAP files |
| 1.0 | April 2026 | Initial release |

---

*Document version: 1.1*
