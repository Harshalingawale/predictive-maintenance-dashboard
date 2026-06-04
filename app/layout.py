# ===============================
# app/layout.py
# Dash App Layout — industrial dark theme (Charcoal + Amber)
# ===============================

from datetime import datetime

import pandas as pd
from dash import dcc, html, dash_table

from app.language import LanguageSystem

# ── Color palette ────────────────────────────────────────────────────────────
COLORS = {
    'background': '#0E0F11',
    'card':       '#16181D',
    'card2':      '#1E2028',
    'border':     '#2A2D35',
    'text':       '#E8EAF0',
    'muted':      '#6B7280',
    'primary':    '#F5A623',
    'primary_dim':'#7A5010',
    'success':    '#34D399',
    'warning':    '#FBBF24',
    'danger':     '#F87171',
    'critical':   '#EF4444',
    'grid':       '#2A2D35',
    'email':      '#A78BFA',
    'shift':      '#34D399',
}

CUSTOM_CSS = (
    "@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500"
    "&family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap');"
    + """
*, *::before, *::after { box-sizing: border-box; }
body { background: #0E0F11; font-family: 'Barlow', sans-serif; color: #E8EAF0; margin: 0; }
body::before { content: ''; display: block; position: fixed; top: 0; left: 0; right: 0;
               height: 3px; background: #F5A623; z-index: 9999; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0E0F11; }
::-webkit-scrollbar-thumb { background: #2A2D35; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #F5A623; }
.kpi-card { border-left: 3px solid #F5A623; background: #16181D; padding: 20px 24px 18px;
            position: relative; overflow: hidden; transition: border-color 0.2s; }
.kpi-card::after { content: ''; position: absolute; top: 0; right: 0; width: 60px; height: 100%;
                   background: linear-gradient(to left, rgba(245,166,35,0.04), transparent); }
.kpi-card:hover { border-color: #FFD580; }
.kpi-card.danger  { border-left-color: #EF4444; }
.kpi-card.danger::after  { background: linear-gradient(to left, rgba(239,68,68,0.04), transparent); }
.kpi-card.success { border-left-color: #34D399; }
.kpi-card.success::after { background: linear-gradient(to left, rgba(52,211,153,0.04), transparent); }
.kpi-card.purple  { border-left-color: #A78BFA; }
.kpi-card.purple::after  { background: linear-gradient(to left, rgba(167,139,250,0.04), transparent); }
.kpi-label { font-family: 'Barlow', sans-serif; font-size: 10px; font-weight: 600;
             letter-spacing: 0.12em; text-transform: uppercase; color: #6B7280; margin-bottom: 8px; }
.kpi-value { font-family: 'Barlow Condensed', sans-serif; font-size: 48px; font-weight: 700;
             line-height: 1; color: #F5A623; }
.kpi-value.danger  { color: #EF4444; }
.kpi-value.success { color: #34D399; }
.kpi-value.purple  { color: #A78BFA; }
.section-header { font-family: 'Barlow Condensed', sans-serif; font-size: 13px; font-weight: 700;
                  letter-spacing: 0.14em; text-transform: uppercase; color: #6B7280;
                  padding-left: 10px; border-left: 2px solid #F5A623; margin-bottom: 14px;
                  margin-top: 0; line-height: 1.3; }
.alert-item { padding: 8px 12px; margin-bottom: 4px; border-left: 3px solid #2A2D35;
              background: #16181D; font-family: 'DM Mono', monospace; font-size: 11px;
              line-height: 1.5; transition: background 0.15s; }
.alert-item:hover  { background: #1E2028; }
.alert-item.critical { border-left-color: #EF4444; background: rgba(239,68,68,0.05); }
.alert-item.high     { border-left-color: #F97316; background: rgba(249,115,22,0.05); }
.alert-item.medium   { border-left-color: #FBBF24; background: rgba(251,191,36,0.05); }
.btn-primary { background: #F5A623; color: #0E0F11; border: none; padding: 10px 20px;
               font-family: 'Barlow', sans-serif; font-size: 13px; font-weight: 600;
               cursor: pointer; transition: background 0.15s; }
.btn-primary:hover { background: #FFD580; }
.btn-ghost { background: transparent; color: #E8EAF0; border: 1px solid #2A2D35;
             padding: 10px 20px; font-family: 'Barlow', sans-serif; font-size: 13px;
             font-weight: 500; cursor: pointer; transition: border-color 0.15s, color 0.15s; }
.btn-ghost:hover { border-color: #F5A623; color: #F5A623; }
.btn-danger { background: transparent; color: #F87171; border: 1px solid #F87171;
              padding: 10px 20px; font-family: 'Barlow', sans-serif; font-size: 13px;
              font-weight: 600; cursor: pointer; }
.btn-danger:hover { background: rgba(248,113,113,0.1); }
.btn-shift { background: #34D399; color: #0E0F11; border: none; padding: 11px 20px;
             font-family: 'Barlow', sans-serif; font-size: 13px; font-weight: 700;
             cursor: pointer; width: 100%; }
.btn-shift:hover { background: #6EE7B7; }
.btn-shift-email { background: transparent; color: #34D399; border: 1px solid #34D399;
                   padding: 10px 20px; font-family: 'Barlow', sans-serif; font-size: 13px;
                   font-weight: 600; cursor: pointer; width: 100%; margin-top: 8px; }
.btn-shift-email:hover { background: rgba(52,211,153,0.08); }
.tab--selected { background: #16181D !important; border-top: 2px solid #F5A623 !important;
                 border-bottom: none !important; border-left: 1px solid #2A2D35 !important;
                 border-right: 1px solid #2A2D35 !important; color: #F5A623 !important;
                 font-family: 'Barlow', sans-serif !important; font-size: 12px !important;
                 font-weight: 600 !important; letter-spacing: 0.06em !important;
                 text-transform: uppercase !important; padding: 12px 16px !important; }
.tab { background: #0E0F11 !important; border: 1px solid #2A2D35 !important;
       color: #6B7280 !important; font-family: 'Barlow', sans-serif !important;
       font-size: 12px !important; font-weight: 500 !important;
       letter-spacing: 0.06em !important; text-transform: uppercase !important;
       padding: 12px 16px !important; }
.tab:hover { color: #E8EAF0 !important; }
.tabs { border-bottom: 1px solid #2A2D35 !important; }
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td {
    font-family: 'DM Mono', monospace !important; font-size: 12px !important; }
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {
    font-family: 'Barlow Condensed', sans-serif !important; font-size: 11px !important;
    letter-spacing: 0.1em !important; text-transform: uppercase !important; }
.Select-control { background-color: #16181D !important; border: 1px solid #2A2D35 !important;
                  color: #E8EAF0 !important; border-radius: 0 !important;
                  font-family: 'Barlow', sans-serif !important; font-size: 13px !important; }
.Select-control:hover { border-color: #F5A623 !important; }
.Select-value-label { color: #E8EAF0 !important; }
.Select-placeholder { color: #6B7280 !important; }
.Select-menu-outer { background-color: #16181D !important; border: 1px solid #2A2D35 !important;
                     border-radius: 0 !important; z-index: 9999 !important; }
.Select-option { background: #16181D !important; color: #E8EAF0 !important;
                 font-family: 'Barlow', sans-serif !important; font-size: 13px !important; }
.Select-option.is-focused { background: #1E2028 !important; }
.Select-option.is-selected { background: rgba(245,166,35,0.15) !important; color: #F5A623 !important; }
.Select--multi .Select-value { background: rgba(245,166,35,0.15) !important;
                                border: 1px solid #7A5010 !important; color: #F5A623 !important;
                                border-radius: 2px !important; font-size: 11px !important; }
.Select-input > input { color: #E8EAF0 !important; font-family: 'Barlow', sans-serif !important; }
.bruss-input { width: 100%; padding: 9px 12px; background: #16181D; color: #E8EAF0;
               border: 1px solid #2A2D35; border-radius: 0; font-family: 'Barlow', sans-serif;
               font-size: 13px; outline: none; transition: border-color 0.15s; }
.bruss-input:focus { border-color: #F5A623; }
.shift-kpi { text-align: center; padding: 14px 8px; background: #0E0F11;
             border: 1px solid #2A2D35; flex: 1; }
.shift-kpi-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em;
                   color: #6B7280; margin-bottom: 6px; font-family: 'Barlow', sans-serif; }
.shift-kpi-value { font-family: 'Barlow Condensed', sans-serif; font-size: 32px;
                   font-weight: 700; line-height: 1; }
"""
)


def build_layout(df: pd.DataFrame, lang_system: LanguageSystem,
                 analytics, shift_report_generator) -> html.Div:
    """Construct and return the full Dash app layout."""

    machine_options = [{'label': m, 'value': m}
                       for m in sorted(df['machine_id'].unique())]

    sidebar = _build_sidebar(df, lang_system, machine_options)
    main    = _build_main_panel(df, lang_system, analytics,
                                shift_report_generator, machine_options)

    return html.Div([
        _build_header(lang_system),
        _build_kpi_strip(df, analytics),
        html.Div([sidebar, main],
                 style={'display': 'flex', 'minHeight': 'calc(100vh - 130px)'}),
        # Stores & Interval
        dcc.Store(id='filtered-data'),
        dcc.Store(id='language-store', data='en'),
        dcc.Store(id='selected-machine-data'),
        dcc.Store(id='auto-schedule-store', data=False),
        dcc.Store(id='last-report-path', data=None),
        dcc.Download(id='shift-report-download'),
        dcc.Interval(id='interval-component', interval=300_000, n_intervals=0, disabled=True),
    ], style={'backgroundColor': COLORS['background'], 'minHeight': '100vh',
              'paddingTop': '3px'})


# ── Sub-builders ─────────────────────────────────────────────────────────────

def _build_header(lang_system: LanguageSystem) -> html.Div:
    return html.Div([
        html.Div([
            html.Div([
                html.Span("BRUSS", style={
                    'fontFamily': "'Barlow Condensed', sans-serif",
                    'fontSize': '28px', 'fontWeight': '700',
                    'letterSpacing': '0.12em', 'color': '#F5A623',
                }),
                html.Span(" INDUSTRIE", style={
                    'fontFamily': "'Barlow Condensed', sans-serif",
                    'fontSize': '28px', 'fontWeight': '300',
                    'letterSpacing': '0.12em', 'color': '#E8EAF0',
                }),
            ]),
            html.Div(id='header-subtitle', style={
                'fontFamily': "'Barlow', sans-serif", 'fontSize': '11px',
                'color': '#6B7280', 'letterSpacing': '0.08em', 'marginTop': '4px',
                'textTransform': 'uppercase',
            }),
        ], style={'flex': '1'}),

        html.Div([
            html.Div(id='header-title', style={'display': 'none'}),
            html.Div(datetime.now().strftime('%A, %d %B %Y'),
                     style={'fontFamily': "'DM Mono', monospace", 'fontSize': '11px',
                            'color': '#6B7280', 'textAlign': 'center'}),
            html.Div('PREDICTIVE MAINTENANCE SYSTEM', style={
                'fontFamily': "'Barlow Condensed', sans-serif", 'fontSize': '13px',
                'color': '#E8EAF0', 'letterSpacing': '0.16em', 'textAlign': 'center',
                'fontWeight': '600', 'marginTop': '3px',
            }),
        ], style={'flex': '1', 'textAlign': 'center'}),

        html.Div([
            dcc.Dropdown(
                id='language-selector',
                options=lang_system.get_language_options(),
                value='en', clearable=False,
                style={'width': '170px', 'backgroundColor': COLORS['card'],
                       'color': COLORS['text'], 'fontSize': '12px'},
            )
        ], style={'flex': '1', 'display': 'flex',
                  'justifyContent': 'flex-end', 'alignItems': 'center'}),

    ], style={
        'display': 'flex', 'alignItems': 'center',
        'padding': '18px 28px 16px',
        'backgroundColor': COLORS['card'],
        'borderBottom': f'1px solid {COLORS["border"]}',
    })


def _build_kpi_strip(df: pd.DataFrame, analytics) -> html.Div:
    avg_health = df['health_score'].mean() if 'health_score' in df.columns else 0
    model_auc  = analytics.models.get('cv_scores', [0])

    cards = [
        ('kpi_total_label',          'kpi_total',          'kpi-card',         'kpi-value'),
        ('kpi_critical_alerts_label','kpi_critical_alerts','kpi-card danger',  'kpi-value danger'),
        ('kpi_email_status_label',   'kpi_email_status',   'kpi-card purple',  'kpi-value purple'),
    ]
    strip = [
        html.Div([
            html.Div(id=lbl_id, className='kpi-label'),
            html.Div(id=val_id, className=val_cls),
        ], className=card_cls, style={'flex': '1'})
        for lbl_id, val_id, card_cls, val_cls in cards
    ] + [
        html.Div([
            html.Div("FLEET AVG HEALTH", className='kpi-label'),
            html.Div(f"{avg_health:.0f}", className='kpi-value success'),
        ], className='kpi-card success', style={'flex': '1'}),
        html.Div([
            html.Div("MODEL AUC", className='kpi-label'),
            html.Div(f"{model_auc.mean():.2f}",
                     style={'fontFamily': "'Barlow Condensed', sans-serif",
                            'fontSize': '48px', 'fontWeight': '700',
                            'color': '#F5A623', 'lineHeight': '1'}),
        ], className='kpi-card', style={'flex': '1'}),
    ]
    return html.Div(strip, style={
        'display': 'flex', 'gap': '1px',
        'backgroundColor': COLORS['border'], 'marginBottom': '1px',
    })


def _label(label_id: str, style_overrides: dict = None) -> html.Label:
    base = {
        'fontSize': '10px', 'color': COLORS['muted'], 'textTransform': 'uppercase',
        'letterSpacing': '0.08em', 'display': 'block', 'marginBottom': '6px',
        'fontFamily': "'Barlow', sans-serif",
    }
    if style_overrides:
        base.update(style_overrides)
    return html.Label(id=label_id, style=base)


def _build_sidebar(df: pd.DataFrame, lang_system: LanguageSystem,
                   machine_options: list) -> html.Div:
    return html.Div([
        # Active alerts
        html.Div([
            html.Div(id='alerts_section_title', className='section-header'),
            html.Div(id='alerts_container',
                     style={'maxHeight': '260px', 'overflowY': 'auto'}),
        ], style={'marginBottom': '28px'}),

        # Filters
        html.Div([
            html.Div("FILTER MACHINES", className='section-header'),
            _label('select_machines_label'),
            dcc.Dropdown(id='machine_filter', options=machine_options, multi=True,
                         placeholder="All machines",
                         style={'backgroundColor': COLORS['card'], 'color': COLORS['text'],
                                'marginBottom': '14px'}),
            _label('select_time_range_label'),
            dcc.DatePickerRange(
                id='date_range',
                start_date=df['timestamp'].min(), end_date=df['timestamp'].max(),
                display_format='YYYY-MM-DD',
                style={'backgroundColor': COLORS['card']},
            ),
        ], style={'marginBottom': '28px'}),

        # Email controls
        html.Div([
            html.Div(id='email_controls_title', className='section-header'),
            _label('test_email_label'),
            dcc.Input(id='test_email_input', type='email',
                      placeholder='recipient@bruss.de', className='bruss-input',
                      style={'marginBottom': '8px', 'display': 'block',
                             'color': '#E8EAF0', 'caretColor': '#F5A623',
                             'backgroundColor': '#16181D', 'border': '1px solid #2A2D35',
                             'padding': '9px 12px', 'width': '100%',
                             'fontFamily': "'Barlow', sans-serif",
                             'fontSize': '13px', 'outline': 'none'}),
            html.Button('Send Test Email', id='send_test_email_button', n_clicks=0,
                        className='btn-ghost',
                        style={'width': '100%', 'marginBottom': '8px'}),
            html.Div([
                html.Button('Daily Report', id='send_daily_report_button', n_clicks=0,
                            className='btn-ghost',
                            style={'flex': '1', 'fontSize': '12px', 'padding': '8px 10px'}),
                html.Button('Critical Alerts', id='send_critical_alerts_button', n_clicks=0,
                            className='btn-danger',
                            style={'flex': '1', 'fontSize': '12px', 'padding': '8px 10px'}),
            ], style={'display': 'flex', 'gap': '6px', 'marginBottom': '8px'}),
            html.Div(id='email_status_feedback',
                     style={'fontSize': '12px', 'fontFamily': "'DM Mono', monospace",
                            'minHeight': '24px', 'color': COLORS['success']}),
        ], style={'marginBottom': '28px'}),

        html.Div(id='email_stats',
                 style={'fontSize': '11px', 'fontFamily': "'DM Mono', monospace",
                        'color': COLORS['muted'], 'lineHeight': '1.8'}),
    ], style={
        'width': '260px', 'flexShrink': '0', 'padding': '24px 20px',
        'backgroundColor': COLORS['card'],
        'borderRight': f'1px solid {COLORS["border"]}',
        'overflowY': 'auto', 'height': 'calc(100vh - 130px)',
        'position': 'sticky', 'top': '0',
    })


def _build_main_panel(df: pd.DataFrame, lang_system: LanguageSystem,
                      analytics, shift_report_generator,
                      machine_options: list) -> html.Div:
    return html.Div([
        dcc.Tabs(id='main-tabs', value='tab-overview', children=[
            _tab_overview(),
            _tab_sensors(),
            _tab_predictions(),
            _tab_maintenance(),
            _tab_email_log(),
            _tab_diagnostics(machine_options),
            _tab_shift_report(shift_report_generator),
        ], style={'backgroundColor': COLORS['background']}),
    ], style={'flex': '1', 'overflowY': 'auto', 'backgroundColor': COLORS['background']})


# ── Individual tabs ───────────────────────────────────────────────────────────

def _tab_overview() -> dcc.Tab:
    return dcc.Tab(label='Overview', value='tab-overview', children=[
        html.Div([
            html.Div([dcc.Graph(id='failure_heatmap', style={'height': '420px'})],
                     style={'marginBottom': '20px'}),
            html.Div([
                html.Div([dcc.Graph(id='health_distribution', style={'height': '320px'})],
                         style={'flex': '1'}),
                html.Div([dcc.Graph(id='risk_pie_chart', style={'height': '320px'})],
                         style={'width': '340px', 'flexShrink': '0'}),
            ], style={'display': 'flex', 'gap': '20px'}),
        ], style={'padding': '20px'}),
    ])


def _tab_sensors() -> dcc.Tab:
    return dcc.Tab(label='Sensors', value='tab-sensor', children=[
        html.Div([
            dcc.Graph(id='sensor_trend', style={'height': '480px', 'marginBottom': '20px'}),
            dcc.Graph(id='vibration_3d', style={'height': '440px'}),
        ], style={'padding': '20px'}),
    ])


def _tab_predictions() -> dcc.Tab:
    return dcc.Tab(label='Predictions', value='tab-predictive', children=[
        html.Div([
            dcc.Graph(id='failure_probability', style={'height': '380px', 'marginBottom': '20px'}),
            html.Div([
                html.Div([dcc.Graph(id='rul_estimation',    style={'height': '360px'})], style={'flex': '3'}),
                html.Div([dcc.Graph(id='feature_importance', style={'height': '360px'})], style={'flex': '2'}),
            ], style={'display': 'flex', 'gap': '20px'}),
        ], style={'padding': '20px'}),
    ])


def _cell_style(bg=None, **kwargs):
    base = {
        'backgroundColor': bg or COLORS['card'], 'color': COLORS['text'],
        'textAlign': 'left', 'padding': '10px 14px',
        'fontFamily': "'DM Mono', monospace", 'fontSize': '12px',
        'border': f'1px solid {COLORS["border"]}',
    }
    base.update(kwargs)
    return base


def _tab_maintenance() -> dcc.Tab:
    return dcc.Tab(label='Maintenance', value='tab-maintenance', children=[
        html.Div([
            html.Div(id='maintenance_title', className='section-header',
                     style={'marginBottom': '16px'}),
            dash_table.DataTable(
                id='maintenance_table',
                columns=[
                    {'name': 'Machine ID',   'id': 'machine_id'},
                    {'name': 'Health',        'id': 'health_score'},
                    {'name': 'Fail. Prob.',   'id': 'failure_prob'},
                    {'name': 'Risk',          'id': 'risk_level'},
                    {'name': 'RUL (hrs)',     'id': 'estimated_rul_hours'},
                    {'name': 'Urgency',       'id': 'maintenance_urgency'},
                    {'name': 'Action',        'id': 'recommended_action'},
                ],
                style_table={'overflowX': 'auto'},
                style_cell=_cell_style(),
                style_header={
                    'backgroundColor': COLORS['background'], 'fontWeight': '700',
                    'color': COLORS['muted'],
                    'fontFamily': "'Barlow Condensed', sans-serif",
                    'fontSize': '11px', 'letterSpacing': '0.1em',
                    'textTransform': 'uppercase',
                    'border': f'1px solid {COLORS["border"]}',
                },
                style_data_conditional=[
                    {'if': {'filter_query': '{maintenance_urgency} = "Immediate"'},
                     'backgroundColor': 'rgba(239,68,68,0.06)', 'color': '#F87171', 'fontWeight': '600'},
                    {'if': {'filter_query': '{maintenance_urgency} = "Scheduled"'}, 'color': '#FBBF24'},
                    {'if': {'row_index': 'odd'}, 'backgroundColor': COLORS['background']},
                ],
                sort_action='native', filter_action='native', page_size=12,
            ),
        ], style={'padding': '20px'}),
    ])


def _tab_email_log() -> dcc.Tab:
    return dcc.Tab(label='Email Log', value='tab-email', children=[
        html.Div([
            html.Div(id='email_history_title', className='section-header',
                     style={'marginBottom': '16px'}),
            dash_table.DataTable(
                id='email_history_table',
                columns=[
                    {'name': 'Timestamp',  'id': 'timestamp'},
                    {'name': 'Machine',    'id': 'machine_id'},
                    {'name': 'Severity',   'id': 'severity'},
                    {'name': 'Subject',    'id': 'subject'},
                    {'name': 'Recipients', 'id': 'sent_to'},
                ],
                style_table={'overflowX': 'auto'},
                style_cell=_cell_style(fontSize='11px'),
                style_header={
                    'backgroundColor': COLORS['background'], 'color': COLORS['muted'],
                    'fontFamily': "'Barlow Condensed', sans-serif",
                    'fontSize': '11px', 'letterSpacing': '0.1em', 'textTransform': 'uppercase',
                    'border': f'1px solid {COLORS["border"]}',
                },
                style_data_conditional=[
                    {'if': {'filter_query': '{severity} = "CRITICAL"'}, 'color': '#F87171', 'fontWeight': '600'},
                    {'if': {'filter_query': '{severity} = "HIGH"'}, 'color': '#FBBF24'},
                    {'if': {'row_index': 'odd'}, 'backgroundColor': COLORS['background']},
                ],
                sort_action='native', filter_action='native', page_size=12,
            ),
        ], style={'padding': '20px'}),
    ])


def _tab_diagnostics(machine_options: list) -> dcc.Tab:
    lbl = lambda lid: html.Label(id=lid, style={
        'fontSize': '10px', 'color': COLORS['muted'], 'textTransform': 'uppercase',
        'letterSpacing': '0.08em', 'display': 'block', 'marginBottom': '6px',
        'fontFamily': "'Barlow', sans-serif",
    })
    dd_style = {'backgroundColor': COLORS['card'], 'color': COLORS['text']}

    return dcc.Tab(label='Diagnostics', value='tab-visual', children=[
        html.Div([
            html.Div(id='visual_diagnostics_title', className='section-header',
                     style={'marginBottom': '16px'}),
            # Controls
            html.Div([
                html.Div([
                    lbl('machine_type_label'),
                    dcc.Dropdown(id='machine_type_selector',
                                 options=[{'label': 'CNC Machine', 'value': 'CNC'},
                                          {'label': 'Robotic End-Effector', 'value': 'REP'}],
                                 value='CNC', clearable=False, style=dd_style),
                ], style={'flex': '1'}),
                html.Div([
                    lbl('machine_id_label'),
                    dcc.Dropdown(id='machine_id_selector', options=machine_options,
                                 placeholder='Select machine ID...', style=dd_style),
                ], style={'flex': '1'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}),

            # Details + status
            html.Div([
                html.Div([
                    html.Div(id='machine_details_label', className='section-header'),
                    html.Div(id='machine_details_display', style={
                        'padding': '16px', 'backgroundColor': COLORS['background'],
                        'border': f'1px solid {COLORS["border"]}',
                        'fontFamily': "'DM Mono', monospace", 'fontSize': '12px',
                        'lineHeight': '2', 'minHeight': '120px',
                    }),
                ], style={'flex': '1'}),
                html.Div([
                    html.Div(id='part_status_label', className='section-header'),
                    html.Div(id='part_status_display', style={
                        'padding': '16px', 'backgroundColor': COLORS['background'],
                        'border': f'1px solid {COLORS["border"]}',
                        'fontFamily': "'DM Mono', monospace", 'fontSize': '12px',
                        'lineHeight': '2', 'minHeight': '120px',
                    }),
                ], style={'flex': '1'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}),

            # Schematic image
            html.Div([
                html.Div(id='machine_schematic_label', className='section-header'),
                html.Img(id='machine_image', style={
                    'width': '100%', 'border': f'1px solid {COLORS["border"]}', 'display': 'block',
                }),
            ], style={'marginBottom': '20px'}),

            # Part alerts
            html.Div([
                html.Div(id='part_alerts_label', className='section-header'),
                html.Div(id='part_alerts_display', style={
                    'padding': '16px', 'backgroundColor': COLORS['background'],
                    'border': f'1px solid {COLORS["border"]}',
                    'fontFamily': "'DM Mono', monospace", 'fontSize': '12px', 'lineHeight': '1.8',
                }),
            ]),
        ], style={'padding': '20px'}),
    ])


def _tab_shift_report(shift_report_generator) -> dcc.Tab:
    return dcc.Tab(label='Shift Report', value='tab-shift', children=[
        html.Div([
            html.Div([
                html.Div(id='shift_report_tab_title', className='section-header'),
                html.Div(id='shift_report_tab_subtitle',
                         style={'fontSize': '11px', 'color': COLORS['muted'],
                                'fontFamily': "'Barlow', sans-serif",
                                'marginTop': '-8px', 'marginBottom': '20px'}),
            ]),
            html.Div([
                # ── LEFT: Controls ─────────────────────────────
                html.Div([
                    html.Div(id='current_shift_display', style={
                        'padding': '14px 16px', 'backgroundColor': COLORS['background'],
                        'border': f'1px solid {COLORS["border"]}',
                        'borderLeft': f'3px solid {COLORS["shift"]}',
                        'fontFamily': "'DM Mono', monospace", 'fontSize': '12px',
                        'marginBottom': '18px',
                    }),
                    html.Label(id='shift_select_label', style={
                        'fontSize': '10px', 'color': COLORS['muted'], 'textTransform': 'uppercase',
                        'letterSpacing': '0.08em', 'display': 'block', 'marginBottom': '6px',
                        'fontFamily': "'Barlow', sans-serif",
                    }),
                    dcc.Dropdown(
                        id='shift_selector',
                        options=[
                            {'label': 'Morning  06:00 – 14:00',   'value': 'morning'},
                            {'label': 'Afternoon  14:00 – 22:00', 'value': 'afternoon'},
                            {'label': 'Night  22:00 – 06:00',     'value': 'night'},
                        ],
                        value=shift_report_generator.get_current_shift(),
                        clearable=False,
                        style={'backgroundColor': COLORS['card'], 'color': COLORS['text'],
                               'marginBottom': '16px'},
                    ),
                    html.Button('Generate PDF Report', id='generate_shift_report_button',
                                n_clicks=0, className='btn-shift'),
                    html.Button('Generate + Email Report', id='email_shift_report_button',
                                n_clicks=0, className='btn-shift-email'),
                    html.Div(id='shift_report_status', style={
                        'marginTop': '12px', 'fontFamily': "'DM Mono', monospace",
                        'fontSize': '11px', 'minHeight': '32px',
                    }),
                    html.Div(id='shift_report_download_section', style={'marginTop': '4px'}),

                    # Auto-scheduler
                    html.Div([
                        html.Div(style={'height': '1px', 'backgroundColor': COLORS['border'],
                                        'margin': '20px 0'}),
                        html.Div("AUTO-SCHEDULE", style={
                            'fontFamily': "'Barlow Condensed', sans-serif",
                            'fontSize': '11px', 'letterSpacing': '0.14em',
                            'color': COLORS['muted'], 'marginBottom': '6px',
                        }),
                        html.Div("Generate PDF automatically at each shift end",
                                 style={'fontSize': '11px', 'color': COLORS['muted'],
                                        'marginBottom': '10px', 'fontFamily': "'Barlow', sans-serif"}),
                        html.Button('Auto-Schedule OFF', id='toggle_auto_schedule_button',
                                    n_clicks=0, className='btn-ghost',
                                    style={'width': '100%', 'fontSize': '12px', 'padding': '9px'}),
                        html.Div(id='auto_schedule_status', style={
                            'marginTop': '6px', 'fontSize': '11px', 'color': COLORS['muted'],
                            'fontFamily': "'DM Mono', monospace",
                        }),
                    ]),
                ], style={
                    'width': '240px', 'flexShrink': '0',
                    'backgroundColor': COLORS['card'],
                    'border': f'1px solid {COLORS["border"]}',
                    'padding': '20px',
                }),

                # ── RIGHT: Preview ──────────────────────────────
                html.Div([
                    # Shift KPI strip
                    html.Div([
                        _shift_kpi("MACHINES",        'shift_kpi_machines',  COLORS['primary']),
                        _shift_kpi("AVG HEALTH",      'shift_kpi_health',    COLORS['success']),
                        _shift_kpi("CRITICAL",        'shift_kpi_critical',  COLORS['danger']),
                        _shift_kpi("IMMEDIATE ACTION",'shift_kpi_immediate', COLORS['warning']),
                    ], style={'display': 'flex', 'gap': '1px',
                              'backgroundColor': COLORS['border'], 'marginBottom': '20px',
                              'border': f'1px solid {COLORS["border"]}'}),

                    # Two-column
                    html.Div([
                        html.Div([
                            html.Div("TOP 5 MACHINES TO HAND OVER", className='section-header'),
                            html.Div(id='shift_top_machines_display', style={
                                'backgroundColor': COLORS['background'],
                                'border': f'1px solid {COLORS["border"]}',
                                'padding': '12px',
                            }),
                        ], style={'flex': '1'}),
                        html.Div([
                            html.Div("ALERT BREAKDOWN", className='section-header'),
                            html.Div(id='shift_alert_breakdown', style={
                                'backgroundColor': COLORS['background'],
                                'border': f'1px solid {COLORS["border"]}',
                                'padding': '12px',
                            }),
                            html.Div(style={'height': '20px'}),
                            html.Div("GENERATED REPORTS", className='section-header'),
                            html.Div(id='previous_reports_list', style={
                                'backgroundColor': COLORS['background'],
                                'border': f'1px solid {COLORS["border"]}',
                                'padding': '12px', 'maxHeight': '180px',
                                'overflowY': 'auto',
                                'fontFamily': "'DM Mono', monospace", 'fontSize': '11px',
                            }),
                        ], style={'flex': '1'}),
                    ], style={'display': 'flex', 'gap': '20px'}),

                ], style={'flex': '1', 'padding': '0 0 0 20px'}),

            ], style={'display': 'flex', 'gap': '0', 'alignItems': 'flex-start'}),
        ], style={'padding': '20px'}),
    ])


def _shift_kpi(label_text: str, value_id: str, color: str) -> html.Div:
    return html.Div([
        html.Div(label_text, className='shift-kpi-label'),
        html.Div(id=value_id, className='shift-kpi-value', style={'color': color}),
    ], className='shift-kpi')