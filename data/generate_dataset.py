"""
data/generate_dataset.py
─────────────────────────
Generates the simulated SAP dataset and saves it to:
    data/BRUSS_SAP_Dataset_Germany_CNC_REP_EN.xlsx

Run from VS Code: F5 → "Regenerate SAP Dataset"
Or terminal:      python data/generate_dataset.py
"""

import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import everything from the full generator script
# (copy bruss_sap_generator_EN.py here and rename the build() call)

import numpy as np
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import random
import warnings
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

np.random.seed(42)
random.seed(42)

# ── All generator functions are imported from the main generator ──────────────
# Place your full bruss_sap_generator_EN.py content here,
# or just import from it if it's in the same folder:

try:
    # If the full generator is in the same data/ folder
    from bruss_sap_generator_EN import (
        gen_equipment_master,
        gen_maintenance_orders,
        gen_notifications,
        gen_measurement_docs,
        gen_spare_parts,
        gen_oee,
        gen_hydra_signals,
        gen_cost_summary,
        gen_mtbf_mttr,
        build,
    )
    print("Imported generator from bruss_sap_generator_EN.py")

except ImportError:
    print("Generator script not found in data/ folder.")
    print("Please copy bruss_sap_generator_EN.py into the data/ folder.")
    print("Then rename it and rerun this script.")
    sys.exit(1)


if __name__ == "__main__":
    # Override output path to save inside the data/ folder
    import bruss_sap_generator_EN as gen
    original_path = "/mnt/user-data/outputs/BRUSS_SAP_Dataset_Germany_CNC_REP_EN.xlsx"
    output_path   = str(Path(__file__).parent / "BRUSS_SAP_Dataset_Germany_CNC_REP_EN.xlsx")

    print(f"Generating dataset → {output_path}")
    build()
    print("Done! Update SAP_EXCEL_PATH in .env if needed.")
