"""
utils/data_loader.py
────────────────────
Loads the SAP Excel dataset into pandas DataFrames.
Supports three modes controlled by DATA_SOURCE in .env:
  - "simulated"  →  generates fresh data on the fly
  - "excel"      →  reads the SAP Excel file from disk
  - "sap_live"   →  placeholder for future SAP RFC/BAPI connection
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class SAPDataLoader:
    """
    Single entry point for all data used by the dashboard.
    Usage:
        loader = SAPDataLoader()
        loader.load()
        df = loader.equipment       # Equipment Master
        df = loader.orders          # PM Orders
        df = loader.master_df       # Joined master DataFrame for ML
    """

    SHEET_NAMES = {
        "equipment":    "🔩 Equipment Master",
        "orders":       "🔧 PM Orders",
        "notifications":"📢 Notifications",
        "measurements": "📏 Measurement Docs",
        "spare_parts":  "🔩 Spare Parts",
        "oee":          "📈 OEE Data",
        "mtbf":         "📊 MTBF-MTTR",
        "hydra":        "📡 Hydra Signals",
        "costs":        "💶 Cost Summary",
    }

    def __init__(self):
        self.source     = os.getenv("DATA_SOURCE", "excel")
        self.excel_path = os.getenv("SAP_EXCEL_PATH", "data/BRUSS_SAP_Dataset_Germany_CNC_REP_EN.xlsx")

        # Public DataFrames – populated after load()
        self.equipment     = None
        self.orders        = None
        self.notifications = None
        self.measurements  = None
        self.spare_parts   = None
        self.oee           = None
        self.mtbf          = None
        self.hydra         = None
        self.costs         = None
        self.master_df     = None

    # ─── Public API ───────────────────────────────────────

    def load(self):
        """Load all sheets and build the master DataFrame."""
        print(f"[DataLoader] Source: {self.source}")

        if self.source == "excel":
            self._load_from_excel()
        elif self.source == "simulated":
            self._load_simulated()
        elif self.source == "sap_live":
            raise NotImplementedError(
                "SAP live connection not yet configured. "
                "Set DATA_SOURCE=excel in .env and use the Excel file for now."
            )

        self._parse_dates()
        self.master_df = self._build_master_df()
        print(f"[DataLoader] Loaded {len(self.equipment)} machines, "
              f"{len(self.orders)} orders, {len(self.measurements)} measurements.")
        return self

    def get_machine(self, equnr: str) -> dict:
        """Get all data for a single machine as a dict."""
        return {
            "info":    self.equipment[self.equipment["EQUNR"] == equnr].iloc[0].to_dict()
                       if not self.equipment[self.equipment["EQUNR"] == equnr].empty else {},
            "orders":  self.orders[self.orders["EQUNR"] == equnr],
            "measurements": self.measurements[self.measurements["EQUNR"] == equnr],
            "oee":     self.oee[self.oee["EQUNR"] == equnr],
            "hydra":   self.hydra[self.hydra["MACHINE_ID"] == equnr],
        }

    def get_cnc_machines(self) -> pd.DataFrame:
        return self.equipment[self.equipment["MACHINE_TYPE"] == "CNC"]

    def get_rep_machines(self) -> pd.DataFrame:
        return self.equipment[self.equipment["MACHINE_TYPE"] == "REP"]

    def get_critical_spare_parts(self) -> pd.DataFrame:
        return self.spare_parts[self.spare_parts["STOCK_STATUS"] == "CRITICAL"]

    def get_open_notifications(self) -> pd.DataFrame:
        return self.notifications[self.notifications["STATUS"] == "OPEN"]

    # ─── Private: Excel Loader ────────────────────────────

    def _load_from_excel(self):
        path = Path(self.excel_path)
        if not path.exists():
            raise FileNotFoundError(
                f"SAP Excel file not found: {path.resolve()}\n"
                f"Run data/generate_dataset.py first to create it."
            )

        print(f"[DataLoader] Reading Excel: {path.name}")
        xl = pd.ExcelFile(path)

        self.equipment     = xl.parse(self.SHEET_NAMES["equipment"])
        self.orders        = xl.parse(self.SHEET_NAMES["orders"])
        self.notifications = xl.parse(self.SHEET_NAMES["notifications"])
        self.measurements  = xl.parse(self.SHEET_NAMES["measurements"])
        self.spare_parts   = xl.parse(self.SHEET_NAMES["spare_parts"])
        self.oee           = xl.parse(self.SHEET_NAMES["oee"])
        self.mtbf          = xl.parse(self.SHEET_NAMES["mtbf"])
        self.hydra         = xl.parse(self.SHEET_NAMES["hydra"])
        self.costs         = xl.parse(self.SHEET_NAMES["costs"])

    # ─── Private: Simulated Loader ────────────────────────

    def _load_simulated(self):
        """Import and run the generator directly — no Excel file needed."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "data"))
        from generate_dataset import (
            gen_equipment_master, gen_maintenance_orders,
            gen_notifications, gen_measurement_docs,
            gen_spare_parts, gen_oee, gen_hydra_signals,
            gen_cost_summary, gen_mtbf_mttr,
        )
        print("[DataLoader] Generating simulated data...")
        eq  = gen_equipment_master(n_cnc=30, n_rep=20)
        ord_= gen_maintenance_orders(eq, n=700)
        self.equipment     = eq
        self.orders        = ord_
        self.notifications = gen_notifications(eq, n=900)
        self.measurements  = gen_measurement_docs(eq, n=4000)
        self.spare_parts   = gen_spare_parts(eq, n=100)
        self.oee           = gen_oee(eq, days=90)
        self.hydra         = gen_hydra_signals(eq)
        self.costs         = gen_cost_summary(ord_)
        self.mtbf          = gen_mtbf_mttr(ord_, eq)

    # ─── Private: Date Parsing ────────────────────────────

    def _parse_dates(self):
        for col in ["ORDER_DATE", "END_DATE"]:
            if col in self.orders.columns:
                self.orders[col] = pd.to_datetime(self.orders[col], errors="coerce")

        if "TIMESTAMP" in self.measurements.columns:
            self.measurements["TIMESTAMP"] = pd.to_datetime(
                self.measurements["TIMESTAMP"], errors="coerce")

        if "DATE" in self.oee.columns:
            self.oee["DATE"] = pd.to_datetime(self.oee["DATE"], errors="coerce")

    # ─── Private: Build Master DataFrame ─────────────────

    def _build_master_df(self) -> pd.DataFrame:
        """
        Join equipment + latest sensor readings + OEE + order history.
        This is the single DataFrame your ML model uses for predictions.
        """
        # Latest value per machine per measurement characteristic
        latest_meas = (
            self.measurements
            .sort_values("TIMESTAMP")
            .groupby(["EQUNR", "CHAR_NAME"])["VALUE"]
            .last()
            .unstack(fill_value=0)
            .reset_index()
        )

        # Latest OEE per machine
        latest_oee = (
            self.oee
            .sort_values("DATE")
            .groupby("EQUNR")[["AVAILABILITY", "PERFORMANCE", "QUALITY", "OEE"]]
            .last()
            .reset_index()
        )

        # Aggregated order history per machine
        order_history = self.orders.groupby("EQUNR").agg(
            TOTAL_ORDERS        = ("ORDER_NO",     "count"),
            CORRECTIVE_ORDERS   = ("ORDER_TYPE",   lambda x: (x == "PM01").sum()),
            TOTAL_DOWNTIME_H    = ("DOWNTIME_H",   "sum"),
            TOTAL_COST_EUR      = ("TOTAL_COST_EUR","sum"),
            LAST_ORDER_DATE     = ("ORDER_DATE",   "max"),
        ).reset_index()

        # Open notifications per machine
        open_notifs = (
            self.notifications[self.notifications["STATUS"] == "OPEN"]
            .groupby("EQUNR")
            .size()
            .reset_index(name="OPEN_NOTIFICATIONS")
        )

        # Join everything onto equipment master
        master = (
            self.equipment
            .merge(latest_meas,   on="EQUNR", how="left")
            .merge(latest_oee,    on="EQUNR", how="left",
                   suffixes=("", "_OEE"))
            .merge(order_history, on="EQUNR", how="left")
            .merge(open_notifs,   on="EQUNR", how="left")
            .merge(
                self.mtbf[["EQUNR", "MTBF_H", "MTTR_H", "RISK_LEVEL"]],
                on="EQUNR", how="left"
            )
        )

        # Derived features
        master["CORRECTIVE_RATIO"] = (
            master["CORRECTIVE_ORDERS"].fillna(0) /
            master["TOTAL_ORDERS"].replace(0, 1).fillna(1)
        )
        master["OPEN_NOTIFICATIONS"] = master["OPEN_NOTIFICATIONS"].fillna(0)

        return master
