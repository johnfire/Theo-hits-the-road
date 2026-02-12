#!/usr/bin/env python3
"""
Raw Spreadsheet Inspection
Shows actual cell values without assuming header structure.
"""

import pandas as pd
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

XLSX_PATH = project_root / "data" / "art-marketing.xlsx"


def inspect_sheet_raw(sheet_name, excel_file, max_rows=10):
    """Show raw data from a sheet."""
    print("-" * 80)
    print(f"SHEET: {sheet_name}")
    print("-" * 80)

    # Read without assuming headers
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)

    print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
    print()

    # Show first N rows completely raw
    print(f"First {min(max_rows, len(df))} rows (raw):")
    print()

    for row_idx in range(min(max_rows, len(df))):
        print(f"Row {row_idx}:")
        row = df.iloc[row_idx]
        for col_idx, val in enumerate(row):
            if pd.notna(val):
                # Truncate long values
                val_str = str(val)
                if len(val_str) > 80:
                    val_str = val_str[:77] + "..."
                print(f"  Col {col_idx:2d}: {val_str}")
        print()

    print()


def main():
    print("=" * 80)
    print("RAW SPREADSHEET INSPECTION")
    print("=" * 80)
    print()

    if not XLSX_PATH.exists():
        print(f"ERROR: File not found: {XLSX_PATH}")
        return

    excel_file = pd.ExcelFile(XLSX_PATH)

    # Focus on the key sheets for import
    priority_sheets = [
        "contacts  leads",      # Main contacts - 593 rows
        "current channels",     # Active galleries - 35 rows
        "show dates",           # Upcoming shows - 31 rows
        "on line",              # Online platforms - 66 rows
    ]

    for sheet_name in priority_sheets:
        if sheet_name in excel_file.sheet_names:
            try:
                inspect_sheet_raw(sheet_name, excel_file, max_rows=15)
            except Exception as e:
                print(f"ERROR inspecting '{sheet_name}': {e}")
                print()

    print("=" * 80)
    print("Want to see other sheets? Available sheets:")
    for i, sheet in enumerate(excel_file.sheet_names, 1):
        row_count = len(pd.read_excel(excel_file, sheet_name=sheet, header=None))
        print(f"  {i:2d}. {sheet:30s} ({row_count:4d} rows)")
    print("=" * 80)


if __name__ == "__main__":
    main()
