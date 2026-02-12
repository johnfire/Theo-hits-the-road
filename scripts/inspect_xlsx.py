#!/usr/bin/env python3
"""
Spreadsheet Inspection Script
Examines art-marketing.xlsx to understand structure before building the importer.
"""

import pandas as pd
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

XLSX_PATH = project_root / "data" / "art-marketing.xlsx"


def inspect_spreadsheet():
    """Examine all sheets in the spreadsheet and report structure."""

    print("=" * 80)
    print("ART-MARKETING.XLSX INSPECTION REPORT")
    print("=" * 80)
    print()

    if not XLSX_PATH.exists():
        print(f"ERROR: File not found: {XLSX_PATH}")
        return

    # Load Excel file
    try:
        excel_file = pd.ExcelFile(XLSX_PATH)
    except Exception as e:
        print(f"ERROR: Could not read Excel file: {e}")
        return

    print(f"File: {XLSX_PATH}")
    print(f"Total sheets: {len(excel_file.sheet_names)}")
    print()

    # Inspect each sheet
    for sheet_name in excel_file.sheet_names:
        print("-" * 80)
        print(f"SHEET: {sheet_name}")
        print("-" * 80)

        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)

            print(f"Rows: {len(df)}")
            print(f"Columns: {len(df.columns)}")
            print()

            print("Column names:")
            for i, col in enumerate(df.columns, 1):
                # Count non-empty values
                non_empty = df[col].notna().sum()
                pct = (non_empty / len(df) * 100) if len(df) > 0 else 0
                print(f"  {i:2d}. {col:40s} ({non_empty:4d}/{len(df):4d} filled, {pct:5.1f}%)")
            print()

            # Show sample data (first 3 non-empty rows)
            if len(df) > 0:
                print("Sample data (first 3 rows with data):")
                # Get first few rows that aren't completely empty
                sample_df = df.dropna(how='all').head(3)
                if len(sample_df) > 0:
                    # Transpose for better readability
                    print(sample_df.T.to_string())
                else:
                    print("  (No data found)")
                print()

            # Look for date-like columns or patterns
            date_candidates = []
            for col in df.columns:
                if any(keyword in str(col).lower() for keyword in ['date', 'datum', 'when', 'wann', 'time', 'zeit', 'updated', 'created']):
                    date_candidates.append(col)

            if date_candidates:
                print(f"Potential date columns: {', '.join(date_candidates)}")
                print()

            # Look for attempt/try columns in contacts sheet
            if 'contact' in sheet_name.lower() or 'lead' in sheet_name.lower():
                attempt_cols = [col for col in df.columns if 'try' in str(col).lower() or 'attempt' in str(col).lower() or 'versuch' in str(col).lower()]
                if attempt_cols:
                    print(f"Found attempt columns: {attempt_cols}")
                    print()
                    # Sample content from attempt columns
                    print("Sample attempt data:")
                    for col in attempt_cols[:5]:  # Show up to 5 attempt columns
                        non_empty_samples = df[col].dropna().head(2)
                        if len(non_empty_samples) > 0:
                            print(f"\n  {col}:")
                            for idx, val in non_empty_samples.items():
                                # Truncate long text
                                val_str = str(val)[:100] + "..." if len(str(val)) > 100 else str(val)
                                print(f"    Row {idx}: {val_str}")
                    print()

        except Exception as e:
            print(f"ERROR reading sheet '{sheet_name}': {e}")
            print()

        print()

    print("=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)


def main():
    inspect_spreadsheet()


if __name__ == "__main__":
    main()
