"""
dashboard.py
────────────
Dash app layout and callbacks.
All data comes from SAPDataLoader — swap DATA_SOURCE in .env
to switch between simulated / Excel / live SAP.
"""

import os
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, callback_context
from dotenv import load_dotenv

from utils.data_loader import SAPDataLoader
from utils.health_score import compute_health_score, health_label, predict_rul, RUL_CONFIG

load_dotenv()

# ─── Colors ──────────────────────────────────────────────────────────────────
COLORS = {
    "bg":       "#F0F4F8",
    "card":     "#FFFFFF",
    "header":   "#1B3A5C",
    "cnc":      "#0D47A1",
    "rep":      "#1B5E20",
    "good":     "#107E3E",
    "warning":  "#E9730C",
    "critical": "#BB0000",
    "blue":     "#0070F2",
    "text":     "#212121",
    "muted":    "#757575",
}

# ─── Data Loading ─────────────────────────────────────────────────────────────
print("[Dashboard] Loading data...")
loader = SAPDataLoader()
loader.load()
master = loader.master_df.copy()
master["HEALTH_SCORE"] = master.apply(compute_health_score, axis=1)
master["HEALTH_LABEL"], master["HEALTH_COLOR"] = zip(
    *master["HEALTH_SCORE"].map(health_label)
)

# ─── ML Model (optional) ──────────────────────────────────────────────────────
models = {}
model_path = Path(os.getenv("MODEL_PATH", "models/failure_model.pkl"))
if model_path.exists():
    models = joblib.load(model_path)
    print(f"[Dashboard] Loaded ML models: {list(models.keys())}")
else:
    print("[Dashboard] No trained model found — run models/train.py first.")

# ─── Helper: Gauge Chart ──────────────────────────────────────────────────────
def make_gauge(value: float, title: str, color: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 13}},
        number={"suffix": "%", "font": {"size": 24, "color": color}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar":  {"color": color},
            "steps": [
                {"range": [0,  40],  "color": "#FFEBEE"},
                {"range": [40, 60],  "color": "#FFF3E0"},
                {"range": [60, 80],  "color": "#E8F5E9"},
                {"range": [80, 100], "color": "#E3F2FD"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "value": value},
        },
    ))
    fig.update_layout(height=180, margin=dict(t=30, b=0, l=20, r=20),
                      paper_bgcolor="white")
    return fig


# ─── Layout Helpers ───────────────────────────────────────────────────────────
def kpi_card(label: str, value: str, color: str = COLORS["header"],
             sub: str = "") -> html.Div:
    return html.Div([
        html.Div(value, style={"fontSize": "28px", "fontWeight": "bold",
                               "color": color}),
        html.Div(label, style={"fontSize": "12px", "color": COLORS["muted"],
                               "marginTop": "2px"}),
        html.Div(sub,   style={"fontSize": "11px", "color": color,
                               "marginTop": "4px"}) if sub else html.Div(),
    ], style={
        "background": COLORS["card"], "borderRadius": "8px",
        "padding": "16px 20px", "boxShadow": "0 1px 4px rgba(0,0,0,0.1)",
        "borderTop": f"4px solid {color}", "flex": "1", "minWidth": "140px",
    })


# ─── App Factory ──────────────────────────────────────────────────────────────
def create_app() -> Dash:
    app = Dash(
        __name__,
        title="BRUSS – Predictive Maintenance",
        suppress_callback_exceptions=True,
    )

    # Machine dropdown options
    machine_options = [
        {
            "label": f"{'🔵' if r['MACHINE_TYPE']=='CNC' else '🟢'} "
                     f"{r['DESCRIPTION']} ({r['PLANT']})",
            "value": r["EQUNR"],
        }
        for _, r in master.sort_values("HEALTH_SCORE").iterrows()
    ]

    # ── Layout ────────────────────────────────────────────
    app.layout = html.Div(style={"background": COLORS["bg"],
                                  "minHeight": "100vh",
                                  "fontFamily": "Arial, sans-serif"}, children=[

        # ── Header ──
        html.Div([
            html.H2("🏭 BRUSS Manufacturing — Predictive Maintenance",
                    style={"color": "white", "margin": 0, "fontSize": "20px"}),
            html.Span(f"Plants: Hamburg • Bremen • Kiel  |  "
                      f"{len(loader.get_cnc_machines())} CNC  |  "
                      f"{len(loader.get_rep_machines())} REP Robots",
                      style={"color": "#B0C4DE", "fontSize": "12px"}),
        ], style={
            "background": COLORS["header"], "padding": "14px 24px",
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "center",
        }),

        # ── Main Content ──
        html.Div(style={"padding": "20px 24px"}, children=[

            # ── Fleet KPIs ──
            html.Div(id="fleet-kpis",
                     style={"display": "flex", "gap": "12px",
                             "flexWrap": "wrap", "marginBottom": "20px"}),

            # ── Machine Selector + Detail ──
            html.Div([

                # Left: Machine List
                html.Div([
                    html.H4("Select Machine", style={"margin": "0 0 10px",
                                                      "color": COLORS["header"]}),
                    dcc.Dropdown(
                        id="machine-selector",
                        options=machine_options,
                        value=machine_options[0]["value"] if machine_options else None,
                        clearable=False,
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(id="machine-health-gauge"),
                    html.Div(id="machine-rul-panel",
                             style={"marginTop": "12px"}),
                    html.Div(id="spare-parts-alert",
                             style={"marginTop": "12px"}),
                ], style={"width": "300px", "flexShrink": 0}),

                # Right: Charts
                html.Div([
                    dcc.Tabs(id="detail-tabs", value="sensors", children=[
                        dcc.Tab(label="📈 Sensor Trend",  value="sensors"),
                        dcc.Tab(label="📊 OEE",           value="oee"),
                        dcc.Tab(label="🔧 Order History", value="orders"),
                    ]),
                    html.Div(id="detail-chart",
                             style={"marginTop": "12px"}),
                ], style={"flex": 1, "minWidth": 0}),

            ], style={"display": "flex", "gap": "20px", "alignItems": "flex-start"}),

            # ── Fleet Overview Chart ──
            html.Div([
                html.H4("Fleet Health Overview",
                        style={"margin": "20px 0 10px", "color": COLORS["header"]}),
                dcc.Graph(id="fleet-chart", style={"height": "320px"}),
            ]),
        ]),

        # ── Refresh interval ──
        dcc.Interval(id="interval", interval=300_000, n_intervals=0),  # 5 min
    ])

    # ── Callbacks ─────────────────────────────────────────

    @app.callback(Output("fleet-kpis", "children"), Input("interval", "n_intervals"))
    def update_kpis(_):
        cnc  = loader.get_cnc_machines()
        rep  = loader.get_rep_machines()
        critical = master[master["HEALTH_SCORE"] < 40]
        open_n   = loader.get_open_notifications()
        crit_sp  = loader.get_critical_spare_parts()
        avg_oee  = loader.oee["OEE"].mean() * 100

        return [
            kpi_card("CNC Machines",       str(len(cnc)),            COLORS["cnc"]),
            kpi_card("REP Robots",          str(len(rep)),            COLORS["rep"]),
            kpi_card("Critical Machines",   str(len(critical)),       COLORS["critical"]),
            kpi_card("Open Notifications",  str(len(open_n)),         COLORS["warning"]),
            kpi_card("Critical Spares",     str(len(crit_sp)),        COLORS["critical"]),
            kpi_card("Fleet Avg OEE",       f"{avg_oee:.1f}%",        COLORS["good"]),
        ]

    @app.callback(
        Output("machine-health-gauge", "children"),
        Output("machine-rul-panel",    "children"),
        Output("spare-parts-alert",    "children"),
        Input("machine-selector", "value"),
    )
    def update_machine_panel(equnr):
        if not equnr:
            return html.Div(), html.Div(), html.Div()

        row   = master[master["EQUNR"] == equnr]
        if row.empty:
            return html.Div("Machine not found"), html.Div(), html.Div()

        row   = row.iloc[0]
        score = row["HEALTH_SCORE"]
        label, color = health_label(score)
        mtype = row["MACHINE_TYPE"]

        # ── Gauge ──
        gauge = dcc.Graph(
            figure=make_gauge(round(score, 1), f"Health Score — {label}", color),
            config={"displayModeBar": False},
            style={"height": "190px"},
        )

        # ── RUL Panel ──
        rul_items = []
        for sig, thresh, direction in RUL_CONFIG.get(mtype, []):
            rul = predict_rul(loader.measurements, equnr, sig,
                              thresh, direction)
            if rul is not None and rul < 9999:
                days   = rul / 16  # assuming 16h production day
                color_ = (COLORS["critical"] if days < 7 else
                           COLORS["warning"]  if days < 30 else
                           COLORS["good"])
                rul_items.append(html.Div([
                    html.Span(f"{sig}:", style={"fontSize": "11px",
                                                "color": COLORS["muted"]}),
                    html.Span(f" {rul:.0f} h ({days:.0f} days)",
                              style={"fontWeight": "bold", "color": color_,
                                     "marginLeft": "6px"}),
                ], style={"marginBottom": "4px"}))

        rul_panel = html.Div([
            html.H5("Remaining Useful Life", style={"margin": "0 0 8px",
                                                      "color": COLORS["header"]}),
            html.Div(rul_items) if rul_items else
            html.Div("Insufficient data for RUL",
                     style={"color": COLORS["muted"], "fontSize": "12px"}),
        ], style={"background": COLORS["card"], "borderRadius": "8px",
                  "padding": "12px", "boxShadow": "0 1px 4px rgba(0,0,0,0.08)"})

        # ── Spare Parts Alert ──
        machine_spares = loader.spare_parts[
            loader.spare_parts["EQUNR"] == equnr
        ]
        critical_sp = machine_spares[machine_spares["STOCK_STATUS"] == "CRITICAL"]

        if len(critical_sp) > 0:
            sp_items = [
                html.Div(f"⚠ {r['DESCRIPTION']} — Stock: {r['STOCK_QTY']} "
                         f"(reorder: {r['REORDER_POINT']})",
                         style={"fontSize": "12px", "color": COLORS["critical"],
                                "marginBottom": "4px"})
                for _, r in critical_sp.iterrows()
            ]
            spare_panel = html.Div([
                html.H5("⚠ Critical Spare Parts",
                        style={"margin": "0 0 8px", "color": COLORS["critical"]}),
                html.Div(sp_items),
            ], style={"background": "#FFEBEE", "borderRadius": "8px",
                      "padding": "12px", "border": f"1px solid {COLORS['critical']}"})
        else:
            spare_panel = html.Div(
                "✅ Spare parts OK",
                style={"background": "#E8F5E9", "borderRadius": "8px",
                       "padding": "12px", "color": COLORS["good"],
                       "fontSize": "13px", "fontWeight": "bold"},
            )

        return gauge, rul_panel, spare_panel

    @app.callback(
        Output("detail-chart", "children"),
        Input("machine-selector", "value"),
        Input("detail-tabs",     "value"),
    )
    def update_detail_chart(equnr, tab):
        if not equnr:
            return html.Div()

        if tab == "sensors":
            meas = loader.measurements[loader.measurements["EQUNR"] == equnr]
            if meas.empty:
                return html.Div("No sensor data", style={"color": COLORS["muted"]})

            # Show all characteristics in subplots
            chars = meas["CHAR_NAME"].unique()[:4]  # top 4 signals
            fig = go.Figure()
            for char in chars:
                sub = meas[meas["CHAR_NAME"] == char].sort_values("TIMESTAMP")
                fig.add_trace(go.Scatter(
                    x=sub["TIMESTAMP"], y=sub["VALUE"],
                    mode="lines", name=char,
                ))
            fig.update_layout(
                title=f"Sensor Readings — {equnr}",
                height=350, margin=dict(t=40, b=40, l=60, r=20),
                legend=dict(orientation="h", y=-0.2),
                paper_bgcolor="white", plot_bgcolor="#F8FBFF",
            )
            return dcc.Graph(figure=fig, config={"displayModeBar": False})

        elif tab == "oee":
            oee = loader.oee[loader.oee["EQUNR"] == equnr].sort_values("DATE")
            if oee.empty:
                return html.Div("No OEE data", style={"color": COLORS["muted"]})

            fig = go.Figure()
            for metric, color in [("AVAILABILITY","#0070F2"),
                                   ("PERFORMANCE","#107E3E"),
                                   ("QUALITY","#E9730C"),
                                   ("OEE","#1B3A5C")]:
                fig.add_trace(go.Scatter(
                    x=oee["DATE"], y=oee[metric] * 100,
                    mode="lines", name=metric, line={"color": color},
                ))
            fig.add_hline(y=85, line_dash="dash", line_color="green",
                          annotation_text="World Class 85%")
            fig.add_hline(y=70, line_dash="dash", line_color="orange",
                          annotation_text="Good 70%")
            fig.update_layout(
                title=f"OEE Trend — {equnr}",
                yaxis_title="Percentage (%)",
                height=350, margin=dict(t=40, b=40, l=60, r=20),
                paper_bgcolor="white", plot_bgcolor="#F8FBFF",
                legend=dict(orientation="h", y=-0.2),
            )
            return dcc.Graph(figure=fig, config={"displayModeBar": False})

        elif tab == "orders":
            orders = (
                loader.orders[loader.orders["EQUNR"] == equnr]
                .sort_values("ORDER_DATE", ascending=False)
                .head(20)
            )
            if orders.empty:
                return html.Div("No orders found", style={"color": COLORS["muted"]})

            cols = ["ORDER_NO","ORDER_DATE","TYPE_DESC","TECHNICIAN",
                    "WORK_HOURS","TOTAL_COST_EUR","STATUS_DESC"]
            available = [c for c in cols if c in orders.columns]
            fig = go.Figure(go.Table(
                header=dict(
                    values=available,
                    fill_color=COLORS["header"],
                    font=dict(color="white", size=11),
                    align="left",
                ),
                cells=dict(
                    values=[orders[c] for c in available],
                    fill_color=[["#EAF2FB" if i%2==0 else "white"
                                 for i in range(len(orders))]],
                    align="left", font=dict(size=10),
                ),
            ))
            fig.update_layout(height=350, margin=dict(t=10, b=10, l=0, r=0))
            return dcc.Graph(figure=fig, config={"displayModeBar": False})

        return html.Div()

    @app.callback(Output("fleet-chart", "figure"), Input("interval", "n_intervals"))
    def update_fleet_chart(_):
        df = master.copy()
        color_map = {"Good": COLORS["good"], "Warning": COLORS["warning"],
                     "Poor": COLORS["critical"], "Critical": COLORS["critical"]}
        df["COLOR"] = df["HEALTH_LABEL"].map(color_map)

        fig = px.bar(
            df.sort_values("HEALTH_SCORE"),
            x="DESCRIPTION", y="HEALTH_SCORE",
            color="HEALTH_LABEL",
            color_discrete_map=color_map,
            hover_data=["MACHINE_TYPE","PLANT","MTBF_H","OEE"],
            labels={"HEALTH_SCORE": "Health Score", "DESCRIPTION": ""},
        )
        fig.add_hline(y=60, line_dash="dash", line_color=COLORS["warning"],
                      annotation_text="Warning threshold")
        fig.add_hline(y=40, line_dash="dash", line_color=COLORS["critical"],
                      annotation_text="Critical threshold")
        fig.update_layout(
            height=300,
            margin=dict(t=10, b=80, l=40, r=20),
            paper_bgcolor="white", plot_bgcolor="#F8FBFF",
            xaxis_tickangle=-35, showlegend=True,
            legend=dict(orientation="h", y=1.1),
        )
        return fig

    return app
