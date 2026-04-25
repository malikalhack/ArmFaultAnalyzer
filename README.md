# ARM Cortex-M Fault Analyzer

A GUI tool for analyzing fault exceptions on ARM Cortex-M microcontrollers.

## Requirements

- Python 3.8+
- Standard library only (tkinter, json, os, sys, re, subprocess, datetime) � no third-party dependencies

## Usage

```bash
python arm_fault_analyzer.py
```

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

Not all fields are required � missing registers default to `0x00000000`.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
|  |  |  |


---

*Document version: 0.3*
