"""
BRUSS Predictive Maintenance Dashboard
=======================================
Single file — everything built in, no extra files needed.

Run:   python app.py
Open:  http://127.0.0.1:8050
"""

import numpy as np
import pandas as pd
import random
import warnings
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output

warnings.filterwarnings("ignore")
np.random.seed(42)
random.seed(42)

# ══════════════════════════════════════════════════════════════════════════════
# 1. DATA GENERATION
# ══════════════════════════════════════════════════════════════════════════════

PLANTS = {
    "PLT_HH": "Hamburg Plant",
    "PLT_BR": "Bremen Plant",
    "PLT_KI": "Kiel Plant",
}

CNC_MODELS = [
    ("DMG MORI",  "DMU 50",         185_000),
    ("DMG MORI",  "NLX 2500",       145_000),
    ("TRUMPF",    "TruLaser 3030",  320_000),
    ("TRUMPF",    "TruBend 5130",   165_000),
    ("Mazak",     "VARIAXIS i-700", 275_000),
    ("Mazak",     "QT-NEXUS 250",   115_000),
    ("Hermle",    "C 400",          340_000),
    ("Heller",    "MCH 250",        395_000),
]

REP_MODELS = [
    ("KUKA",    "KR 6 R900",       58_000),
    ("KUKA",    "KR QUANTEC 120", 115_000),
    ("FANUC",   "R-2000iC/165F",   95_000),
    ("FANUC",   "M-20iD/12",       68_000),
    ("ABB",     "IRB 6700-150",   108_000),
    ("ABB",     "IRB 2600-12",     62_000),
    ("Yaskawa", "AR1440",          88_000),
]

TECHNICIANS = [
    "Mueller_M", "Schmidt_K", "Weber_T", "Fischer_A", "Wagner_S",
    "Becker_J",  "Hoffmann_R","Schaefer_L","Koch_P",  "Richter_F",
]

DAMAGE_CNC = [
    "Elevated spindle vibration",    "Coolant temperature too high",
    "Critical tool wear detected",   "X-axis positioning error",
    "Z-axis servo fault",            "Hydraulic pressure drop",
    "Coolant lubricant leakage",     "Encoder drift detected",
    "Linear bearing worn",           "Ball screw backlash increased",
]

DAMAGE_REP = [
    "Elevated J1 axis vibration",    "J2 gearbox backlash increased",
    "Weld seam quality degraded",    "J6 gripper force too low",
    "Servo drive overheating",       "Collision protection triggered",
    "Positioning accuracy degraded", "Force-torque sensor drift",
    "Safety light curtain alarm",    "Reference point deviation",
]


def generate_all_data():
    print("[Data] Generating simulated SAP data...")

    # Equipment Master
    equipment_rows = []
    for i in range(30):
        m = random.choice(CNC_MODELS)
        install = datetime(2017, 1, 1) + timedelta(days=random.randint(0, 2000))
        equipment_rows.append({
            "EQUNR":        f"EQ-{10000+i}",
            "DESCRIPTION":  f"{m[0]} {m[1]} #{i+1:02d}",
            "MACHINE_TYPE": "CNC",
            "MANUFACTURER": m[0],
            "MODEL":        m[1],
            "PLANT":        random.choice(list(PLANTS)),
            "INSTALL_DATE": install.strftime("%Y-%m-%d"),
            "ACQ_VALUE":    m[2],
            "CRITICALITY":  random.choices(["A","B","C"], weights=[0.2,0.5,0.3])[0],
        })
    for i in range(20):
        m = random.choice(REP_MODELS)
        install = datetime(2018, 1, 1) + timedelta(days=random.randint(0, 1800))
        equipment_rows.append({
            "EQUNR":        f"EQ-{10030+i}",
            "DESCRIPTION":  f"{m[0]} {m[1]} #{i+1:02d}",
            "MACHINE_TYPE": "REP",
            "MANUFACTURER": m[0],
            "MODEL":        m[1],
            "PLANT":        random.choice(list(PLANTS)),
            "INSTALL_DATE": install.strftime("%Y-%m-%d"),
            "ACQ_VALUE":    m[2],
            "CRITICALITY":  random.choices(["A","B","C"], weights=[0.3,0.4,0.3])[0],
        })
    equipment = pd.DataFrame(equipment_rows)

    # PM Orders
    order_rows = []
    for i in range(700):
        eq    = equipment.sample(1).iloc[0]
        otype = random.choices(["PM01","PM02","PM03","PM04"],
                               weights=[0.30, 0.40, 0.18, 0.12])[0]
        date  = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 450))
        dur   = random.uniform(4, 96) if otype in ["PM01","PM04"] else random.uniform(1, 12)
        cost  = random.uniform(800, 25000) if otype in ["PM01","PM04"] else random.uniform(150, 5000)
        order_rows.append({
            "ORDER_NO":       f"PM-{200000+i}",
            "ORDER_TYPE":     otype,
            "TYPE_DESC":      {"PM01":"Corrective","PM02":"Preventive",
                               "PM03":"Inspection","PM04":"Overhaul"}[otype],
            "EQUNR":          eq["EQUNR"],
            "MACHINE_NAME":   eq["DESCRIPTION"],
            "MACHINE_TYPE":   eq["MACHINE_TYPE"],
            "PLANT":          eq["PLANT"],
            "ORDER_DATE":     date.strftime("%Y-%m-%d"),
            "WORK_HOURS":     round(dur, 1),
            "TOTAL_COST_EUR": round(cost, 2),
            "TECHNICIAN":     random.choice(TECHNICIANS),
            "STATUS":         random.choices(["CRTD","REL","TECO","CLSD"],
                                             weights=[0.05, 0.25, 0.35, 0.35])[0],
            "DOWNTIME_H":     round(dur * 0.65 if otype == "PM01" else dur * 0.25, 1),
        })
    orders = pd.DataFrame(order_rows)
    orders["ORDER_DATE"] = pd.to_datetime(orders["ORDER_DATE"])

    # Notifications
    notif_rows = []
    for i in range(900):
        eq     = equipment.sample(1).iloc[0]
        closed = random.random() > 0.22
        damage = random.choice(DAMAGE_CNC if eq["MACHINE_TYPE"] == "CNC" else DAMAGE_REP)
        date   = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 450))
        notif_rows.append({
            "NOTIF_NO":    f"N-{300000+i}",
            "EQUNR":       eq["EQUNR"],
            "MACHINE_NAME":eq["DESCRIPTION"],
            "MACHINE_TYPE":eq["MACHINE_TYPE"],
            "PLANT":       eq["PLANT"],
            "NOTIF_DATE":  date.strftime("%Y-%m-%d"),
            "SHORT_TEXT":  damage,
            "STATUS":      "CLOSED" if closed else "OPEN",
            "PRIORITY":    random.choice(["1","2","3","4"]),
        })
    notifications = pd.DataFrame(notif_rows)

    # Measurements
    CNC_SIGNALS = {
        "SPINDLE_SPEED_RPM": (8000, 0,    200,  True),
        "SPINDLE_LOAD_PCT":  (65,   0,    8,    True),
        "COOLANT_TEMP_C":    (22,   0,    2,    True),
        "X_VIBRATION_MMS":   (1.5,  0.01, 0.4,  True),
        "Y_VIBRATION_MMS":   (1.2,  0.01, 0.3,  True),
        "TOOL_WEAR_PCT":     (30,   1.0,  1,    True),
        "POWER_KW":          (15,   0,    3,    False),
    }
    REP_SIGNALS = {
        "J1_VIBRATION_MMS":  (0.8,  0.005, 0.2,  True),
        "J2_BACKLASH_DEG":   (0.02, 0.001, 0.01, True),
        "J3_TEMPERATURE_C":  (45,   0,     3,    True),
        "WELD_QUALITY_PCT":  (96,  -0.05,  1,    True),
        "GRIPPER_FORCE_N":   (450, -0.5,   20,   True),
        "POWER_KW":          (4.5,  0,     0.5,  False),
    }
    meas_rows = []
    sample_eq = equipment.sample(min(20, len(equipment)))
    for _, eq in sample_eq.iterrows():
        signals = CNC_SIGNALS if eq["MACHINE_TYPE"] == "CNC" else REP_SIGNALS
        state   = {k: v[0] for k, v in signals.items()}
        deg     = random.uniform(0, 0.8)
        for d in range(200):
            ts  = datetime(2024, 1, 1) + timedelta(hours=d * 3)
            sig = random.choice(list(signals))
            base, drift, std, can_deg = signals[sig]
            state[sig] += drift + np.random.normal(0, std * 0.3)
            if can_deg:
                state[sig] += deg * std * 0.1
            anomaly = random.random() < 0.03
            val = state[sig] * (1 + random.uniform(0.4, 1.2)) if anomaly else state[sig]
            meas_rows.append({
                "EQUNR":        eq["EQUNR"],
                "MACHINE_NAME": eq["DESCRIPTION"],
                "MACHINE_TYPE": eq["MACHINE_TYPE"],
                "CHAR_NAME":    sig,
                "TIMESTAMP":    ts,
                "VALUE":        round(float(max(0, val)), 4),
                "ANOMALY":      "YES" if anomaly else "NO",
            })
    measurements = pd.DataFrame(meas_rows)

    # Spare Parts
    SPARES = {
        "CNC": [
            ("SP-CNC-001","Deep Groove Ball Bearing 6205",  "BEARING",   18.50),
            ("SP-CNC-002","Angular Contact Bearing 7210",   "BEARING",   95.00),
            ("SP-CNC-003","Spindle Motor 7.5kW Siemens",    "MOTOR",   2250.00),
            ("SP-CNC-004","X-Axis Servo Motor Fanuc",       "MOTOR",   1890.00),
            ("SP-CNC-005","Coolant Pump Assembly",          "PUMP",     340.00),
            ("SP-CNC-006","Ball Screw 32x5",                "MECH",    1100.00),
            ("SP-CNC-007","Carbide Insert Set VHM",         "TOOLING",   22.50),
            ("SP-CNC-008","Hydraulic Filter 10µm",          "FILTER",    58.00),
        ],
        "REP": [
            ("SP-REP-001","Harmonic Drive Gearbox J2 KUKA", "GEARBOX",  3200.00),
            ("SP-REP-002","Servo Motor Axis J1 FANUC",      "MOTOR",    2800.00),
            ("SP-REP-003","MIG/MAG Welding Torch 500A",     "WELDING",   385.00),
            ("SP-REP-004","Gripper Finger Schunk EGP",      "GRIPPER",   145.00),
            ("SP-REP-005","Cable Harness Axis J4 KUKA",     "CABLING",   620.00),
            ("SP-REP-006","Torque Sensor 200Nm",            "SENSOR",    980.00),
            ("SP-REP-007","Cooling Fan Robot Controller",   "COOLING",   125.00),
            ("SP-REP-008","Safety Light Curtain Receiver",  "SAFETY",   1200.00),
        ],
    }
    spare_rows = []
    for _ in range(80):
        mtype = random.choice(["CNC","REP"])
        part  = random.choice(SPARES[mtype])
        eq    = equipment[equipment["MACHINE_TYPE"] == mtype].sample(1).iloc[0]
        stock = random.randint(0, 30)
        reord = random.randint(2, 6)
        spare_rows.append({
            "MATERIAL_NO":   part[0],
            "DESCRIPTION":   part[1],
            "CATEGORY":      part[2],
            "MACHINE_TYPE":  mtype,
            "EQUNR":         eq["EQUNR"],
            "MACHINE_NAME":  eq["DESCRIPTION"],
            "PLANT":         eq["PLANT"],
            "STOCK_QTY":     stock,
            "REORDER_POINT": reord,
            "STOCK_STATUS":  ("CRITICAL" if stock < reord else
                              "LOW"      if stock < reord * 2 else "OK"),
            "UNIT_PRICE_EUR":part[3],
        })
    spare_parts = pd.DataFrame(spare_rows)

    # OEE
    oee_rows = []
    sample_eq2 = equipment.sample(min(20, len(equipment)))
    for _, eq in sample_eq2.iterrows():
        mtype = eq["MACHINE_TYPE"]
        ba, bp, bq = (0.93, 0.91, 0.98) if mtype == "REP" else (0.90, 0.87, 0.96)
        for d in range(90):
            date  = datetime(2024, 1, 1) + timedelta(days=d)
            trend = d / 90
            avail = float(np.clip(np.random.normal(ba - trend*0.05, 0.025), 0.5, 1.0))
            perf  = float(np.clip(np.random.normal(bp - trend*0.04, 0.035), 0.5, 1.0))
            qual  = float(np.clip(np.random.normal(bq - trend*0.02, 0.010), 0.85, 1.0))
            oee   = round(avail * perf * qual, 4)
            oee_rows.append({
                "EQUNR":        eq["EQUNR"],
                "MACHINE_NAME": eq["DESCRIPTION"],
                "MACHINE_TYPE": mtype,
                "PLANT":        eq["PLANT"],
                "DATE":         date,
                "AVAILABILITY": round(avail, 4),
                "PERFORMANCE":  round(perf, 4),
                "QUALITY":      round(qual, 4),
                "OEE":          oee,
                "OEE_CLASS":    ("WORLD CLASS"      if oee >= 0.85 else
                                 "GOOD"             if oee >= 0.70 else
                                 "AVERAGE"          if oee >= 0.60 else
                                 "NEEDS IMPROVEMENT"),
                "DOWNTIME_H":   round(16 * (1 - avail), 2),
            })
    oee = pd.DataFrame(oee_rows)

    print(f"[Data] Done — {len(equipment)} machines | {len(orders)} orders | "
          f"{len(measurements)} measurements | {len(oee)} OEE records")

    return dict(equipment=equipment, orders=orders, notifications=notifications,
                measurements=measurements, spare_parts=spare_parts, oee=oee)


# ══════════════════════════════════════════════════════════════════════════════
# 2. HEALTH SCORE & RUL
# ══════════════════════════════════════════════════════════════════════════════

CNC_W = {"TOOL_WEAR_PCT":0.35, "X_VIBRATION_MMS":0.25, "Y_VIBRATION_MMS":0.15,
         "SPINDLE_LOAD_PCT":0.15, "COOLANT_TEMP_C":0.10}
CNC_T = {"TOOL_WEAR_PCT":(70,90), "X_VIBRATION_MMS":(3.5,6.0),
         "Y_VIBRATION_MMS":(3.0,5.5), "SPINDLE_LOAD_PCT":(80,95), "COOLANT_TEMP_C":(35,45)}

REP_W = {"J1_VIBRATION_MMS":0.25, "J2_BACKLASH_DEG":0.25,
         "WELD_QUALITY_PCT":0.25, "GRIPPER_FORCE_N":0.15, "J3_TEMPERATURE_C":0.10}
REP_T = {"J1_VIBRATION_MMS":(1.5,3.0,"up"), "J2_BACKLASH_DEG":(0.08,0.15,"up"),
         "WELD_QUALITY_PCT":(90,80,"down"), "GRIPPER_FORCE_N":(380,300,"down"),
         "J3_TEMPERATURE_C":(55,70,"up")}

RUL_CONFIG = {
    "CNC": [("TOOL_WEAR_PCT",90,"up"), ("X_VIBRATION_MMS",6.0,"up")],
    "REP": [("J2_BACKLASH_DEG",0.15,"up"), ("WELD_QUALITY_PCT",80,"down"),
            ("GRIPPER_FORCE_N",300,"down")],
}


def compute_health(row):
    mtype = row.get("MACHINE_TYPE", "CNC")
    W, T  = (CNC_W, CNC_T) if mtype == "CNC" else (REP_W, REP_T)
    penalty = total_w = 0.0
    for sig, w in W.items():
        val = row.get(sig, np.nan)
        if pd.isna(val):
            continue
        total_w += w
        t = T[sig]
        warn, crit = t[0], t[1]
        direction  = "up" if mtype == "CNC" else t[2]
        if direction == "up":
            if val <= warn:       penalty += w * 0.05
            elif val <= crit:
                ratio = (val - warn) / (crit - warn)
                penalty += w * (ratio**1.5) * 0.6
            else:                 penalty += w * 0.9
        else:
            if val >= warn:       penalty += w * 0.05
            elif val >= crit:
                ratio = (warn - val) / (warn - crit)
                penalty += w * (ratio**1.5) * 0.6
            else:                 penalty += w * 0.9
    if total_w == 0:
        return 50.0
    return float(np.clip(100 * (1 - penalty / total_w), 0, 100))


def health_label(score):
    if score >= 80: return "Good",     "#107E3E"
    if score >= 60: return "Warning",  "#E9730C"
    if score >= 40: return "Poor",     "#CC4400"
    return              "Critical", "#BB0000"


def predict_rul(meas_df, equnr, signal, threshold, direction="up"):
    data = (meas_df[(meas_df["EQUNR"]==equnr) & (meas_df["CHAR_NAME"]==signal)]
            .sort_values("TIMESTAMP").tail(30))
    if len(data) < 5:
        return None
    vals  = data["VALUE"].values
    slope = np.polyfit(range(len(vals)), vals, 1)[0]
    curr  = vals[-1]
    if direction == "up":
        if slope <= 0: return 9999.0
        steps = (threshold - curr) / slope
    else:
        if slope >= 0: return 9999.0
        steps = (curr - threshold) / abs(slope)
    return round(max(0.0, steps * 3), 1)


# ══════════════════════════════════════════════════════════════════════════════
# 3. BUILD MASTER DATAFRAME
# ══════════════════════════════════════════════════════════════════════════════

def build_master(data):
    latest_meas = (data["measurements"].sort_values("TIMESTAMP")
                   .groupby(["EQUNR","CHAR_NAME"])["VALUE"]
                   .last().unstack(fill_value=np.nan).reset_index())
    latest_oee  = (data["oee"].sort_values("DATE")
                   .groupby("EQUNR")[["AVAILABILITY","PERFORMANCE","QUALITY","OEE"]]
                   .last().reset_index())
    order_hist  = data["orders"].groupby("EQUNR").agg(
        TOTAL_ORDERS      = ("ORDER_NO",       "count"),
        CORRECTIVE_ORDERS = ("ORDER_TYPE",     lambda x: (x=="PM01").sum()),
        TOTAL_DOWNTIME_H  = ("DOWNTIME_H",     "sum"),
        TOTAL_COST_EUR    = ("TOTAL_COST_EUR", "sum"),
    ).reset_index()
    open_notifs = (data["notifications"][data["notifications"]["STATUS"]=="OPEN"]
                   .groupby("EQUNR").size().reset_index(name="OPEN_NOTIFS"))

    master = (data["equipment"]
              .merge(latest_meas, on="EQUNR", how="left")
              .merge(latest_oee,  on="EQUNR", how="left")
              .merge(order_hist,  on="EQUNR", how="left")
              .merge(open_notifs, on="EQUNR", how="left"))

    master["CORRECTIVE_RATIO"] = (master["CORRECTIVE_ORDERS"].fillna(0) /
                                   master["TOTAL_ORDERS"].replace(0,1).fillna(1))
    master["OPEN_NOTIFS"]  = master["OPEN_NOTIFS"].fillna(0)
    master["HEALTH_SCORE"] = master.apply(compute_health, axis=1)
    master["HEALTH_LABEL"] = master["HEALTH_SCORE"].apply(lambda s: health_label(s)[0])
    master["HEALTH_COLOR"] = master["HEALTH_SCORE"].apply(lambda s: health_label(s)[1])
    return master


# ══════════════════════════════════════════════════════════════════════════════
# 4. UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

CLR = {"bg":"#F0F4F8","card":"#FFFFFF","header":"#1B3A5C","cnc":"#0D47A1",
       "rep":"#1B5E20","good":"#107E3E","warning":"#E9730C","critical":"#BB0000",
       "blue":"#0070F2","muted":"#757575"}
CARD = {"background":CLR["card"],"borderRadius":"8px","padding":"16px 20px",
        "boxShadow":"0 1px 6px rgba(0,0,0,0.10)"}


def kpi_card(label, value, color):
    return html.Div([
        html.Div(value, style={"fontSize":"26px","fontWeight":"bold","color":color}),
        html.Div(label, style={"fontSize":"12px","color":CLR["muted"],"marginTop":"3px"}),
    ], style={**CARD,"borderTop":f"4px solid {color}","flex":"1","minWidth":"130px"})


def gauge_fig(value, title, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        title={"text":title,"font":{"size":12}},
        number={"suffix":"%","font":{"size":22,"color":color}},
        gauge={"axis":{"range":[0,100]},"bar":{"color":color},
               "steps":[{"range":[0,40],"color":"#FFEBEE"},
                        {"range":[40,60],"color":"#FFF3E0"},
                        {"range":[60,80],"color":"#E8F5E9"},
                        {"range":[80,100],"color":"#E3F2FD"}]},
    ))
    fig.update_layout(height=180, margin=dict(t=28,b=0,l=20,r=20), paper_bgcolor="white")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 5. GENERATE DATA
# ══════════════════════════════════════════════════════════════════════════════

DATA   = generate_all_data()
MASTER = build_master(DATA)

# ══════════════════════════════════════════════════════════════════════════════
# 6. DASH APP
# ══════════════════════════════════════════════════════════════════════════════

app = Dash(__name__, title="BRUSS – Predictive Maintenance",
           suppress_callback_exceptions=True)

machine_opts = [
    {"label": f"{'🔵' if r['MACHINE_TYPE']=='CNC' else '🟢'} "
              f"{r['DESCRIPTION']} ({PLANTS.get(r['PLANT'], r['PLANT'])})",
     "value": r["EQUNR"]}
    for _, r in MASTER.sort_values("HEALTH_SCORE").iterrows()
]

app.layout = html.Div(style={"background":CLR["bg"],"minHeight":"100vh",
                              "fontFamily":"Arial, sans-serif"}, children=[

    # Header
    html.Div([
        html.Div([
            html.H2("🏭 BRUSS Manufacturing — Predictive Maintenance",
                    style={"color":"white","margin":0,"fontSize":"19px"}),
            html.Span(f"Hamburg • Bremen • Kiel  |  "
                      f"{len(MASTER[MASTER['MACHINE_TYPE']=='CNC'])} CNC  |  "
                      f"{len(MASTER[MASTER['MACHINE_TYPE']=='REP'])} REP Robots",
                      style={"color":"#B0C4DE","fontSize":"12px"}),
        ]),
        html.Div(datetime.now().strftime("%d/%m/%Y %H:%M"),
                 style={"color":"#B0C4DE","fontSize":"12px"}),
    ], style={"background":CLR["header"],"padding":"14px 24px",
              "display":"flex","justifyContent":"space-between","alignItems":"center"}),

    html.Div(style={"padding":"20px 24px"}, children=[

        # KPI row
        html.Div(id="kpi-row",
                 style={"display":"flex","gap":"12px",
                        "flexWrap":"wrap","marginBottom":"20px"}),

        # Machine panel + detail
        html.Div([
            # Left
            html.Div([
                html.H4("Select Machine",
                        style={"margin":"0 0 10px","color":CLR["header"]}),
                dcc.Dropdown(id="machine-dd", options=machine_opts,
                             value=machine_opts[0]["value"] if machine_opts else None,
                             clearable=False, style={"marginBottom":"12px"}),
                html.Div(id="health-gauge"),
                html.Div(id="rul-panel",   style={"marginTop":"12px"}),
                html.Div(id="spare-panel", style={"marginTop":"12px"}),
            ], style={"width":"300px","flexShrink":0}),

            # Right
            html.Div([
                dcc.Tabs(id="tabs", value="sensors", children=[
                    dcc.Tab(label="📈 Sensor Trend",  value="sensors"),
                    dcc.Tab(label="📊 OEE",           value="oee"),
                    dcc.Tab(label="🔧 Order History", value="orders"),
                ]),
                html.Div(id="tab-content", style={"marginTop":"12px"}),
            ], style={"flex":1,"minWidth":0}),

        ], style={"display":"flex","gap":"20px","alignItems":"flex-start"}),

        # Fleet chart
        html.Div([
            html.H4("Fleet Health Overview — All Machines",
                    style={"margin":"20px 0 10px","color":CLR["header"]}),
            dcc.Graph(id="fleet-chart", style={"height":"300px"}),
        ]),
    ]),

    dcc.Interval(id="tick", interval=300_000, n_intervals=0),
])


# Callbacks

@app.callback(Output("kpi-row","children"), Input("tick","n_intervals"))
def update_kpis(_):
    cnc     = MASTER[MASTER["MACHINE_TYPE"]=="CNC"]
    rep     = MASTER[MASTER["MACHINE_TYPE"]=="REP"]
    crit    = MASTER[MASTER["HEALTH_SCORE"] < 40]
    open_n  = DATA["notifications"][DATA["notifications"]["STATUS"]=="OPEN"]
    crit_sp = DATA["spare_parts"][DATA["spare_parts"]["STOCK_STATUS"]=="CRITICAL"]
    oee_avg = DATA["oee"]["OEE"].mean() * 100
    return [
        kpi_card("CNC Machines",      str(len(cnc)),     CLR["cnc"]),
        kpi_card("REP Robots",         str(len(rep)),     CLR["rep"]),
        kpi_card("Critical Machines",  str(len(crit)),    CLR["critical"]),
        kpi_card("Open Notifications", str(len(open_n)),  CLR["warning"]),
        kpi_card("Critical Spares",    str(len(crit_sp)), CLR["critical"]),
        kpi_card("Fleet Avg OEE",      f"{oee_avg:.1f}%", CLR["good"]),
    ]


@app.callback(
    Output("health-gauge","children"),
    Output("rul-panel","children"),
    Output("spare-panel","children"),
    Input("machine-dd","value"),
)
def update_left(equnr):
    if not equnr:
        return html.Div(), html.Div(), html.Div()
    row = MASTER[MASTER["EQUNR"]==equnr]
    if row.empty:
        return html.Div("Not found"), html.Div(), html.Div()
    row   = row.iloc[0]
    score = row["HEALTH_SCORE"]
    label, color = health_label(score)
    mtype = row["MACHINE_TYPE"]

    gauge = dcc.Graph(figure=gauge_fig(round(score,1), f"Health — {label}", color),
                      config={"displayModeBar":False}, style={"height":"190px"})

    rul_items = []
    for sig, thresh, direction in RUL_CONFIG.get(mtype, []):
        rul = predict_rul(DATA["measurements"], equnr, sig, thresh, direction)
        if rul is not None and rul < 9999:
            days = rul / 16
            c = CLR["critical"] if days < 7 else (CLR["warning"] if days < 30 else CLR["good"])
            rul_items.append(html.Div([
                html.Div(sig, style={"fontSize":"11px","color":CLR["muted"]}),
                html.Div(f"{rul:.0f} h  ({days:.0f} days)",
                         style={"fontWeight":"bold","color":c,"fontSize":"14px"}),
            ], style={"marginBottom":"8px","padding":"6px",
                      "background":CLR["bg"],"borderRadius":"4px"}))

    rul_panel = html.Div([
        html.H5("Remaining Useful Life",
                style={"margin":"0 0 8px","color":CLR["header"]}),
        html.Div(rul_items) if rul_items
        else html.Div("Not enough data yet",
                      style={"color":CLR["muted"],"fontSize":"12px"}),
    ], style=CARD)

    sp = DATA["spare_parts"][DATA["spare_parts"]["EQUNR"]==equnr]
    crit_sp = sp[sp["STOCK_STATUS"]=="CRITICAL"]
    if len(crit_sp):
        items = [html.Div(f"⚠ {r['DESCRIPTION']}  —  Stock: {r['STOCK_QTY']} "
                          f"(min: {r['REORDER_POINT']})",
                          style={"fontSize":"12px","color":CLR["critical"],
                                 "marginBottom":"4px"})
                 for _, r in crit_sp.iterrows()]
        spare_panel = html.Div([
            html.H5("⚠ Critical Spare Parts",
                    style={"margin":"0 0 8px","color":CLR["critical"]}),
            html.Div(items),
        ], style={**CARD,"border":f"1px solid {CLR['critical']}","background":"#FFEBEE"})
    else:
        spare_panel = html.Div("✅ Spare parts OK",
                               style={**CARD,"color":CLR["good"],"fontWeight":"bold",
                                      "background":"#E8F5E9"})
    return gauge, rul_panel, spare_panel


@app.callback(
    Output("tab-content","children"),
    Input("machine-dd","value"),
    Input("tabs","value"),
)
def update_tab(equnr, tab):
    if not equnr:
        return html.Div()

    if tab == "sensors":
        meas = DATA["measurements"][DATA["measurements"]["EQUNR"]==equnr]
        if meas.empty:
            return html.Div("No sensor data", style={"color":CLR["muted"],"padding":"20px"})
        fig = go.Figure()
        for char in meas["CHAR_NAME"].unique()[:5]:
            sub = meas[meas["CHAR_NAME"]==char].sort_values("TIMESTAMP")
            fig.add_trace(go.Scatter(x=sub["TIMESTAMP"], y=sub["VALUE"],
                                     mode="lines", name=char))
        fig.update_layout(title=f"Sensor Readings — {equnr}", height=360,
                          margin=dict(t=40,b=60,l=60,r=20),
                          paper_bgcolor="white", plot_bgcolor="#F8FBFF",
                          legend=dict(orientation="h",y=-0.25))
        return dcc.Graph(figure=fig, config={"displayModeBar":False})

    elif tab == "oee":
        oee = DATA["oee"][DATA["oee"]["EQUNR"]==equnr].sort_values("DATE")
        if oee.empty:
            return html.Div("No OEE data", style={"color":CLR["muted"],"padding":"20px"})
        fig = go.Figure()
        for metric, c in [("AVAILABILITY","#0070F2"),("PERFORMANCE","#107E3E"),
                           ("QUALITY","#E9730C"),("OEE","#1B3A5C")]:
            fig.add_trace(go.Scatter(x=oee["DATE"], y=oee[metric]*100,
                                     mode="lines", name=metric, line={"color":c}))
        fig.add_hline(y=85, line_dash="dash", line_color="green",
                      annotation_text="World Class 85%")
        fig.add_hline(y=70, line_dash="dash", line_color="orange",
                      annotation_text="Good 70%")
        fig.update_layout(title=f"OEE Trend — {equnr}", yaxis_title="(%)",
                          height=360, margin=dict(t=40,b=60,l=60,r=20),
                          paper_bgcolor="white", plot_bgcolor="#F8FBFF",
                          legend=dict(orientation="h",y=-0.25))
        return dcc.Graph(figure=fig, config={"displayModeBar":False})

    elif tab == "orders":
        orders = (DATA["orders"][DATA["orders"]["EQUNR"]==equnr]
                  .sort_values("ORDER_DATE", ascending=False).head(20))
        if orders.empty:
            return html.Div("No orders found", style={"color":CLR["muted"],"padding":"20px"})
        cols = ["ORDER_NO","ORDER_DATE","TYPE_DESC","TECHNICIAN",
                "WORK_HOURS","TOTAL_COST_EUR","STATUS"]
        fig = go.Figure(go.Table(
            header=dict(values=cols, fill_color=CLR["header"],
                        font=dict(color="white",size=11), align="left"),
            cells=dict(values=[orders[c] for c in cols],
                       fill_color=[["#EAF2FB" if i%2==0 else "white"
                                    for i in range(len(orders))]],
                       align="left", font=dict(size=10)),
        ))
        fig.update_layout(height=360, margin=dict(t=10,b=10,l=0,r=0))
        return dcc.Graph(figure=fig, config={"displayModeBar":False})

    return html.Div()


@app.callback(Output("fleet-chart","figure"), Input("tick","n_intervals"))
def update_fleet(_):
    df = MASTER.copy().sort_values("HEALTH_SCORE")
    color_map = {"Good":CLR["good"],"Warning":CLR["warning"],
                 "Poor":CLR["critical"],"Critical":CLR["critical"]}
    fig = px.bar(df, x="DESCRIPTION", y="HEALTH_SCORE",
                 color="HEALTH_LABEL", color_discrete_map=color_map,
                 hover_data=["MACHINE_TYPE","PLANT","OEE"],
                 labels={"HEALTH_SCORE":"Health Score","DESCRIPTION":""})
    fig.add_hline(y=60, line_dash="dash", line_color=CLR["warning"],
                  annotation_text="Warning")
    fig.add_hline(y=40, line_dash="dash", line_color=CLR["critical"],
                  annotation_text="Critical")
    fig.update_layout(height=280, margin=dict(t=10,b=100,l=40,r=20),
                      paper_bgcolor="white", plot_bgcolor="#F8FBFF",
                      xaxis_tickangle=-40,
                      legend=dict(orientation="h",y=1.1))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 7. RUN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  BRUSS Predictive Maintenance Dashboard")
    print("  Open browser → http://127.0.0.1:8050")
    print("="*55 + "\n")
    app.run(host="127.0.0.1", port=8050, debug=True)
