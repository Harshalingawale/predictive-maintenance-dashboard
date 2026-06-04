# ===============================
# app/callbacks.py
# All Dash callbacks — wired to layout IDs in layout.py
# ===============================

import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import Input, Output, State, callback_context, dcc
from plotly.subplots import make_subplots

from app.layout import COLORS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _alert_to_div(alert: dict, lang_system) -> object:
    """Render a single alert dict as a Dash Div."""
    from dash import html
    color_map = {
        'CRITICAL': COLORS['danger'], 'HIGH': '#FF5722',
        'MEDIUM': COLORS['warning'], 'LOW': COLORS['success'], 'INFO': COLORS['primary'],
    }
    color = color_map.get(alert['severity'], COLORS['text'])
    if 'message_key' in alert:
        message = lang_system.get_text(alert['message_key'],
                                       *alert.get('message_params', []))
    else:
        message = alert.get('message', '')
    return html.Div([
        html.Span(f"{alert['timestamp'].strftime('%H:%M:%S')} — ",
                  style={'color': COLORS['text'], 'opacity': '0.7'}),
        html.Span(f"[{alert['severity']}] ",
                  style={'color': color, 'fontWeight': 'bold'}),
        html.Span(message, style={'color': COLORS['text']}),
    ], style={'marginBottom': '5px', 'padding': '5px',
              'borderLeft': f'3px solid {color}',
              'backgroundColor': f'{color}10'})


def _apply_filter(df: pd.DataFrame, filter_spec: dict) -> pd.DataFrame:
    """Re-apply the filter spec on the server-side dataframe. Fast — no JSON round-trip."""
    if not filter_spec:
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    machines = filter_spec.get('machines')
    if machines:
        mask &= df['machine_id'].isin(machines)
    start = filter_spec.get('start_date')
    end   = filter_spec.get('end_date')
    if start and end:
        mask &= (df['timestamp'] >= start) & (df['timestamp'] <= end)
    return df[mask]


def register_callbacks(app, df: pd.DataFrame, analytics,
                        email_system, alert_engine,
                        visual_diagnostics, shift_report_generator,
                        lang_system):
    """Register all callbacks against the Dash app instance."""

    # ── Language store ────────────────────────────────────────────────────────
    @app.callback(
        Output('language-store', 'data'),
        Input('language-selector', 'value'),
    )
    def update_language_store(language):
        return language if language in ['en', 'de'] else 'en'

    # ── Static text (driven by language) ─────────────────────────────────────
    @app.callback(
        [Output('header-title', 'children'),
         Output('header-subtitle', 'children'),
         Output('kpi_total_label', 'children'),
         Output('kpi_critical_alerts_label', 'children'),
         Output('kpi_email_status_label', 'children'),
         Output('email_controls_title', 'children'),
         Output('test_email_label', 'children'),
         Output('alerts_section_title', 'children'),
         Output('select_machines_label', 'children'),
         Output('select_time_range_label', 'children'),
         Output('maintenance_title', 'children'),
         Output('email_history_title', 'children'),
         Output('visual_diagnostics_title', 'children'),
         Output('machine_type_label', 'children'),
         Output('machine_id_label', 'children'),
         Output('machine_details_label', 'children'),
         Output('part_status_label', 'children'),
         Output('machine_schematic_label', 'children'),
         Output('part_alerts_label', 'children'),
         Output('shift_report_tab_title', 'children'),
         Output('shift_report_tab_subtitle', 'children'),
         Output('shift_select_label', 'children')],
        Input('language-store', 'data'),
    )
    def update_static_text(language):
        lang_system.set_language(language)
        alert_engine.set_language(language)
        visual_diagnostics.set_language(language)
        shift_report_generator.set_language(language)
        T = lang_system.get_text
        return [
            T('dashboard_title'), T('dashboard_subtitle'),
            T('total_machines'), T('critical_alerts'), T('email_status'),
            T('email_controls'), T('test_email_recipient'), T('recent_alerts'),
            T('select_machines'), T('select_time_range'),
            T('maintenance_recommendations'), T('email_alert_history'),
            T('visual_diagnostics'), T('select_machine_type'), T('select_machine_id'),
            T('machine_details'), T('part_status'), T('machine_schematic'), T('part_alerts'),
            T('shift_report_title'), T('shift_report_subtitle'), T('shift_select_label'),
        ]

    # ── KPIs, filtered data, alerts ───────────────────────────────────────────
    @app.callback(
        [Output('kpi_total', 'children'),
         Output('kpi_critical_alerts', 'children'),
         Output('kpi_email_status', 'children'),
         Output('filtered-data', 'data'),
         Output('alerts_container', 'children'),
         Output('email_stats', 'children'),
         Output('selected-machine-data', 'data')],
        [Input('machine_filter', 'value'),
         Input('date_range', 'start_date'),
         Input('date_range', 'end_date'),
         Input('interval-component', 'n_intervals'),
         Input('language-store', 'data'),
         Input('machine_id_selector', 'value')],
    )
    def update_kpis_and_data(machines, start_date, end_date, _n,
                             language, selected_machine_id):
        from dash import html
        lang_system.set_language(language)

        # Apply filters directly on server-side df — no copy of full dataframe
        mask = pd.Series([True] * len(df), index=df.index)
        if machines:
            mask &= df['machine_id'].isin(machines)
        if start_date and end_date:
            mask &= (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
        dff = df[mask]

        total_machines = dff['machine_id'].nunique()
        summary        = alert_engine.get_alert_summary()
        critical_count = summary['critical'] + summary['high']
        email_stats    = email_system.get_alert_stats(24)
        email_status   = f"📨 {email_stats['total_alerts']}"

        # Alert list
        filtered_alerts = [a for a in alert_engine.alerts
                           if not machines or a['machine_id'] in machines]
        alert_els = [_alert_to_div(a, lang_system) for a in filtered_alerts[-10:]]
        if not alert_els:
            alert_els = [html.Div(lang_system.get_text('no_recent_alerts'),
                                  style={'color': COLORS['text'], 'opacity': '0.7'})]

        # Email stats block
        stats_block = html.Div([
            html.H5(lang_system.get_text('email_stats'), style={'marginBottom': '10px'}),
            html.Div([
                html.Span(f"{lang_system.get_text('total_sent')} ", style={'opacity': '0.7'}),
                html.Span(str(email_stats['total_alerts']),
                          style={'color': COLORS['email'], 'fontWeight': 'bold', 'marginRight': '20px'}),
                html.Span(f"{lang_system.get_text('critical')}: ", style={'opacity': '0.7'}),
                html.Span(str(email_stats['by_severity'].get('CRITICAL', 0)),
                          style={'color': COLORS['danger'], 'fontWeight': 'bold', 'marginRight': '20px'}),
                html.Span(f"{lang_system.get_text('last_alert')} ", style={'opacity': '0.7'}),
                html.Span(
                    email_stats['last_alert'].strftime('%H:%M')
                    if email_stats['last_alert'] else lang_system.get_text('never'),
                    style={'color': COLORS['primary'], 'fontWeight': 'bold'},
                ),
            ]),
        ])

        # Selected machine data
        machine_data = _extract_machine_data(dff, selected_machine_id)

        # Store only a tiny filter spec — NOT the full dataframe
        # Each chart callback will re-apply the filter on the server-side df directly
        filter_spec = {
            'machines': machines or [],
            'start_date': str(start_date) if start_date else None,
            'end_date': str(end_date) if end_date else None,
        }

        return (
            str(total_machines), str(critical_count), email_status,
            filter_spec,
            alert_els, stats_block, machine_data,
        )

    # ── Shift preview panel ───────────────────────────────────────────────────
    @app.callback(
        [Output('current_shift_display', 'children'),
         Output('shift_kpi_machines', 'children'),
         Output('shift_kpi_health', 'children'),
         Output('shift_kpi_critical', 'children'),
         Output('shift_kpi_immediate', 'children'),
         Output('shift_top_machines_display', 'children'),
         Output('shift_alert_breakdown', 'children'),
         Output('previous_reports_list', 'children')],
        [Input('shift_selector', 'value'),
         Input('interval-component', 'n_intervals'),
         Input('language-store', 'data')],
    )
    def update_shift_preview(shift_key, _n, language):
        from dash import html
        lang_system.set_language(language)
        current = shift_report_generator.get_current_shift()
        shift_key = shift_key or current
        info      = shift_report_generator.SHIFT_DEFINITIONS[shift_key]
        s_start, s_end = shift_report_generator.get_shift_time_range(shift_key)

        is_active   = shift_key == current
        shift_label = info['label_de' if language == 'de' else 'label']

        # Current shift badge
        badge = html.Div([
            html.Div([
                html.Span("🟢 " if is_active else "⚪ ", style={'fontSize': '18px'}),
                html.Span(shift_label, style={
                    'fontWeight': 'bold', 'fontSize': '15px',
                    'color': COLORS['shift'] if is_active else COLORS['text'],
                }),
                html.Span(" (ACTIVE)" if is_active else "",
                          style={'color': COLORS['shift'], 'fontSize': '12px', 'marginLeft': '8px'}),
            ], style={'marginBottom': '6px'}),
            html.Div(f"Window: {s_start.strftime('%d %b %Y %H:%M')} – {s_end.strftime('%H:%M')}",
                     style={'fontSize': '12px', 'opacity': '0.7', 'color': COLORS['text']}),
        ])

        # Data for shift window
        sdf = df.copy()
        if 'timestamp' in sdf.columns:
            mask = (sdf['timestamp'] >= s_start) & (sdf['timestamp'] <= s_end)
            sdf  = sdf[mask] if mask.sum() >= 10 else sdf.tail(300)
        else:
            sdf = sdf.tail(300)

        total_machines = sdf['machine_id'].nunique() if 'machine_id' in sdf.columns else 0
        avg_health     = sdf['health_score'].mean() if 'health_score' in sdf.columns else 0
        health_color   = (COLORS['success'] if avg_health >= 70
                          else COLORS['warning'] if avg_health >= 50
                          else COLORS['danger'])

        s_alerts   = [a for a in alert_engine.alerts if s_start <= a['timestamp'] <= s_end]
        s_alerts   = s_alerts or alert_engine.alerts[-50:]
        crit       = sum(1 for a in s_alerts if a['severity'] == 'CRITICAL')
        high       = sum(1 for a in s_alerts if a['severity'] == 'HIGH')
        medium     = sum(1 for a in s_alerts if a['severity'] == 'MEDIUM')
        immediate  = (
            sdf[sdf['maintenance_urgency_en'] == 'Immediate']['machine_id'].nunique()
            if 'maintenance_urgency_en' in sdf.columns else 0
        )

        # Top 5 machines
        top5_els = []
        if 'failure_prob' in sdf.columns:
            top5 = sdf.sort_values('failure_prob', ascending=False).drop_duplicates('machine_id').head(5)
            for _, row in top5.iterrows():
                fp  = row.get('failure_prob', 0)
                hs  = row.get('health_score', 0)
                urg = row.get('maintenance_urgency_en', 'Monitor')
                urg_color = (COLORS['danger'] if urg == 'Immediate'
                             else COLORS['warning'] if urg == 'Scheduled'
                             else COLORS['success'])
                fp_color  = (COLORS['danger'] if fp > 0.7
                             else COLORS['warning'] if fp > 0.4
                             else COLORS['success'])
                top5_els.append(html.Div([
                    html.Span(f"🔧 {row['machine_id']}",
                              style={'fontWeight': 'bold', 'color': COLORS['text'], 'fontSize': '13px'}),
                    html.Span(f" | Health: {hs:.1f}",
                              style={'color': COLORS['text'], 'opacity': '0.7', 'fontSize': '12px'}),
                    html.Span(f" | Fail Prob: {fp:.1%}",
                              style={'color': fp_color, 'fontSize': '12px', 'fontWeight': 'bold'}),
                    html.Span(f" [{urg}]",
                              style={'color': urg_color, 'fontSize': '11px',
                                     'fontWeight': 'bold', 'marginLeft': '6px'}),
                ], style={'padding': '6px 0', 'borderBottom': f'1px solid {COLORS["grid"]}'}))
        top5_els = top5_els or [html.Div("No data", style={'color': COLORS['text'], 'opacity': '0.5'})]

        alert_breakdown = html.Div([
            html.Div([
                html.Span("🔴 CRITICAL: ", style={'color': COLORS['danger'], 'fontWeight': 'bold'}),
                html.Span(str(crit), style={'color': COLORS['danger'], 'fontSize': '18px',
                                            'fontWeight': 'bold', 'marginRight': '20px'}),
                html.Span("🟠 HIGH: ", style={'color': '#FF5722', 'fontWeight': 'bold'}),
                html.Span(str(high), style={'color': '#FF5722', 'fontSize': '18px',
                                            'fontWeight': 'bold', 'marginRight': '20px'}),
                html.Span("🟡 MEDIUM: ", style={'color': COLORS['warning'], 'fontWeight': 'bold'}),
                html.Span(str(medium), style={'color': COLORS['warning'], 'fontSize': '18px',
                                              'fontWeight': 'bold'}),
            ], style={'marginBottom': '8px'}),
            html.Div(f"Total shift alerts: {len(s_alerts)}",
                     style={'fontSize': '12px', 'color': COLORS['text'], 'opacity': '0.7'}),
        ])

        # Previous reports list
        prev_reports = []
        if os.path.exists("shift_reports"):
            for fname in sorted(
                [f for f in os.listdir("shift_reports") if f.endswith('.pdf')],
                reverse=True,
            )[:8]:
                prev_reports.append(html.Div([
                    html.Span("📄 "),
                    html.Span(fname, style={'fontSize': '11px', 'color': COLORS['primary']}),
                ], style={'padding': '4px 0', 'borderBottom': f'1px solid {COLORS["grid"]}'}))
        prev_reports = prev_reports or [
            html.Div("No reports generated yet.",
                     style={'color': COLORS['text'], 'opacity': '0.5', 'fontSize': '12px'})
        ]

        return (badge, str(total_machines), f"{avg_health:.1f}",
                str(crit), str(immediate),
                top5_els, alert_breakdown, prev_reports)

    # ── Generate shift report ─────────────────────────────────────────────────
    @app.callback(
        [Output('shift_report_status', 'children'),
         Output('shift_report_download_section', 'children'),
         Output('last-report-path', 'data'),
         Output('shift-report-download', 'data')],
        [Input('generate_shift_report_button', 'n_clicks'),
         Input('email_shift_report_button', 'n_clicks')],
        [State('shift_selector', 'value'),
         State('language-store', 'data')],
        prevent_initial_call=True,
    )
    def handle_shift_report_generation(gen_clicks, email_clicks, shift_key, language):
        from dash import html
        ctx = callback_context
        if not ctx.triggered:
            return "", html.Div(), None, None
        lang_system.set_language(language)
        shift_report_generator.set_language(language)
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        try:
            pdf_path  = shift_report_generator.generate_pdf(df, alert_engine, shift_key)
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            filename   = os.path.basename(pdf_path)
            email_sent = False
            if button_id == 'email_shift_report_button':
                email_sent = shift_report_generator._email_report(
                    pdf_path, shift_key, email_system)

            key = 'shift_report_emailed' if email_sent else 'shift_report_generated'
            status_msg = html.Div([
                html.Span("✅ ", style={'fontSize': '18px'}),
                html.Span(lang_system.get_text(key),
                          style={'color': COLORS['success'], 'fontWeight': 'bold'}),
                *([html.Br(),
                   html.Span(f"Saved: {filename}",
                             style={'fontSize': '11px', 'opacity': '0.7',
                                    'color': COLORS['text']})]
                  if not email_sent else []),
            ], style={'padding': '10px', 'backgroundColor': '#1B5E20', 'borderRadius': '6px'})

            download_section = html.Div([
                html.Hr(style={'borderColor': COLORS['grid'], 'margin': '10px 0'}),
                html.Button(
                    f"⬇️ {lang_system.get_text('download_report')}",
                    id='download_report_trigger_button', n_clicks=0,
                    style={'backgroundColor': COLORS['primary'], 'color': 'white',
                           'border': 'none', 'padding': '10px 16px',
                           'cursor': 'pointer', 'width': '100%', 'fontSize': '13px'},
                ),
                html.Div(f"File: {filename}",
                         style={'fontSize': '10px', 'opacity': '0.6',
                                'color': COLORS['text'], 'marginTop': '4px',
                                'textAlign': 'center'}),
            ])
            return (status_msg, download_section, pdf_path,
                    dcc.send_bytes(pdf_bytes, filename))
        except Exception as e:
            from dash import html
            error_msg = html.Div([
                html.Span("❌ ", style={'fontSize': '18px'}),
                html.Span(f"{lang_system.get_text('shift_report_failed')}: {e}",
                          style={'color': COLORS['danger']}),
            ], style={'padding': '10px', 'backgroundColor': '#B71C1C22', 'borderRadius': '6px'})
            return error_msg, html.Div(), None, None

    # ── Toggle auto-scheduler ─────────────────────────────────────────────────
    @app.callback(
        [Output('toggle_auto_schedule_button', 'children'),
         Output('toggle_auto_schedule_button', 'style'),
         Output('auto_schedule_status', 'children'),
         Output('auto-schedule-store', 'data')],
        Input('toggle_auto_schedule_button', 'n_clicks'),
        State('auto-schedule-store', 'data'),
        prevent_initial_call=True,
    )
    def toggle_auto_schedule(n_clicks, is_active):
        new_state = not bool(is_active)
        if new_state:
            shift_report_generator.start_auto_scheduler(df, alert_engine, email_system)
            return ('🟢 Auto-Schedule ON',
                    {'backgroundColor': COLORS['shift'], 'color': 'white', 'border': 'none',
                     'padding': '10px 16px', 'cursor': 'pointer', 'width': '100%', 'fontSize': '13px'},
                    "⏰ Will auto-generate PDFs at 6:00, 14:00, and 22:00", new_state)
        else:
            shift_report_generator.stop_auto_scheduler()
            return ('⚫ Auto-Schedule OFF',
                    {'backgroundColor': COLORS['grid'], 'color': 'white', 'border': 'none',
                     'padding': '10px 16px', 'cursor': 'pointer', 'width': '100%', 'fontSize': '13px'},
                    "Auto-schedule is disabled", new_state)

    # ── Email actions ─────────────────────────────────────────────────────────
    @app.callback(
        Output('email_status_feedback', 'children'),
        [Input('send_test_email_button', 'n_clicks'),
         Input('send_daily_report_button', 'n_clicks'),
         Input('send_critical_alerts_button', 'n_clicks'),
         Input('language-store', 'data')],
        State('test_email_input', 'value'),
    )
    def handle_email_actions(test_clicks, daily_clicks, critical_clicks, language, test_email):
        from dash import html
        ctx = callback_context
        if not ctx.triggered:
            return ""
        lang_system.set_language(language)
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if button_id == 'send_test_email_button' and test_email:
            orig = email_system.config['receiver_emails']
            email_system.config['receiver_emails'] = [test_email]
            ok = email_system.send_email_alert({
                'severity': 'INFO', 'title': lang_system.get_text('test_alert_title'),
                'message': lang_system.get_text('test_alert_message', test_email),
                'machine_id': 'TEST', 'metrics': {'Status': 'Test OK'},
            })
            email_system.config['receiver_emails'] = orig
            color = COLORS['success'] if ok else COLORS['danger']
            msg   = "✅ Test email sent!" if ok else "❌ Failed. Check email config."
            return html.Div(msg, style={'color': color, 'padding': '10px'})

        if button_id == 'send_daily_report_button':
            alert_engine.send_daily_report(email_system, df)
            return html.Div("✅ Daily report sent!", style={'color': COLORS['success'], 'padding': '10px'})

        if button_id == 'send_critical_alerts_button':
            result = alert_engine.send_critical_alerts(email_system)
            if result['sent'] > 0:
                return html.Div(f"✅ Sent {result['sent']} critical alerts!",
                                style={'color': COLORS['success'], 'padding': '10px'})
            return html.Div("ℹ️ No critical alerts or failed.",
                            style={'color': COLORS['primary'], 'padding': '10px'})
        return ""

    # ── Maintenance table ─────────────────────────────────────────────────────
    @app.callback(
        Output('maintenance_table', 'data'),
        [Input('filtered-data', 'data'), Input('language-store', 'data'),
         Input('main-tabs', 'value')],
    )
    def update_maintenance_table(data, language, active_tab):
        if active_tab != 'tab-maintenance':
            raise dash.exceptions.PreventUpdate
        if not data or not isinstance(data, dict):
            return []
        dff = _apply_filter(df, data)
        lang_system.set_language(language)
        required = ['machine_id', 'health_score', 'failure_prob', 'estimated_rul_hours']
        if any(c not in dff.columns for c in required):
            return []

        risk_col    = 'risk_level_de'    if language == 'de' else 'risk_level_en'
        urgency_col = 'maintenance_urgency_de' if language == 'de' else 'maintenance_urgency_en'
        dff['risk_level_display']          = dff.get(risk_col,    'Unknown')
        dff['maintenance_urgency_display'] = dff.get(urgency_col, 'Monitor')

        def get_rec(row):
            urg = row['maintenance_urgency_display']
            if language == 'de':
                return {'Sofort': "Sofortige Wartung planen",
                        'Geplant': "Wartung innerhalb 7 Tagen"}.get(urg, "Regelmäßige Überwachung")
            return {'Immediate': "Schedule immediate maintenance",
                    'Scheduled': "Schedule within 7 days"}.get(urg, "Regular monitoring")

        dff['recommended_action'] = dff.apply(get_rec, axis=1)
        out = (dff.sort_values('failure_prob', ascending=False).head(50)
               [['machine_id', 'health_score', 'failure_prob', 'risk_level_display',
                 'estimated_rul_hours', 'maintenance_urgency_display', 'recommended_action']]
               .copy())
        out.columns = ['machine_id', 'health_score', 'failure_prob', 'risk_level',
                       'estimated_rul_hours', 'maintenance_urgency', 'recommended_action']
        out['failure_prob']       = out['failure_prob'].apply(lambda x: f"{x:.1%}")
        out['health_score']       = out['health_score'].apply(lambda x: f"{x:.1f}")
        out['estimated_rul_hours']= out['estimated_rul_hours'].apply(lambda x: f"{x:.0f}")
        return out.to_dict('records')

    # ── Email history table ───────────────────────────────────────────────────
    @app.callback(
        Output('email_history_table', 'data'),
        [Input('interval-component', 'n_intervals'), Input('language-store', 'data')],
    )
    def update_email_history(_n, _lang):
        return [
            {'timestamp':  a['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
             'machine_id': a['machine_id'],
             'severity':   a['severity'],
             'subject':    a['subject'],
             'sent_to':    ', '.join(a['sent_to'][:2]) + ('...' if len(a['sent_to']) > 2 else '')}
            for a in email_system.alert_history[-50:]
        ]

    # ── Visual diagnostics ────────────────────────────────────────────────────
    @app.callback(
        [Output('machine_image', 'src'),
         Output('machine_details_display', 'children'),
         Output('part_status_display', 'children'),
         Output('part_alerts_display', 'children')],
        [Input('machine_type_selector', 'value'),
         Input('selected-machine-data', 'data'),
         Input('language-store', 'data')],
    )
    def update_visual_diagnostics(machine_type, machine_data, language):
        from dash import html
        lang_system.set_language(language)
        visual_diagnostics.set_language(language)

        part_status = (visual_diagnostics.analyze_machine_data(machine_data)
                       if machine_data and 'tool_wear' in machine_data else {})
        machine_id   = (machine_data or {}).get('machine_id', '')
        health_score = (machine_data or {}).get('health_score', 100)
        failure_prob = (machine_data or {}).get('failure_prob', 0)
        data_type    = (machine_data or {}).get('machine_type', 'M')
        actual_type  = machine_type or ('REP' if data_type == 'L' else 'CNC')

        img_src = visual_diagnostics.generate_machine_image(
            actual_type, part_status, machine_id, health_score, failure_prob)

        if machine_data and 'machine_id' in machine_data:
            hc = (COLORS['success'] if health_score >= 60
                  else COLORS['warning'] if health_score >= 40 else COLORS['danger'])
            fc = (COLORS['success'] if failure_prob <= 0.3
                  else COLORS['warning'] if failure_prob <= 0.6 else COLORS['danger'])
            details = [
                html.Div([html.Span("Machine ID: ", style={'opacity': '0.7'}),
                          html.Span(machine_id, style={'color': COLORS['primary'], 'fontWeight': 'bold'})],
                         style={'marginBottom': '5px'}),
                html.Div([html.Span("Health: ", style={'opacity': '0.7'}),
                          html.Span(f"{health_score:.1f}", style={'color': hc, 'fontWeight': 'bold'})],
                         style={'marginBottom': '5px'}),
                html.Div([html.Span("Failure Prob: ", style={'opacity': '0.7'}),
                          html.Span(f"{failure_prob:.1%}", style={'color': fc, 'fontWeight': 'bold'})]),
            ]
        else:
            details = [html.Div(lang_system.get_text('no_data_for_machine'), style={'opacity': '0.7'})]

        crit_n = sum(1 for s in part_status.values() if s == 'critical')
        warn_n = sum(1 for s in part_status.values() if s == 'warning')
        status_els = [html.Div([
            html.Span(f"🔴 {crit_n} critical  ", style={'color': COLORS['danger']}),
            html.Span(f"🟡 {warn_n} warning",  style={'color': COLORS['warning']}),
        ])]

        recs = []
        if machine_data:
            if machine_data.get('tool_wear', 0) > 200:
                recs.append(f"Check spindle — tool wear: {machine_data['tool_wear']:.0f} min")
            if machine_data.get('temp_differential', 0) > 10:
                recs.append(f"Check coolant — temp diff: {machine_data['temp_differential']:.1f} K")
            if machine_data.get('vibration_magnitude', 0) > 5:
                recs.append(f"Check ball screw — vibration: {machine_data['vibration_magnitude']:.2f}")
        alert_els = (
            [html.Div([html.Span("• "), html.Span(r)]) for r in recs]
            or [html.Div("✅ No immediate maintenance required", style={'color': COLORS['success']})]
        )
        return img_src, details, status_els, alert_els

    # ── Overview charts ───────────────────────────────────────────────────────
    @app.callback(
        [Output('health_distribution', 'figure'),
         Output('risk_pie_chart', 'figure'),
         Output('failure_heatmap', 'figure')],
        [Input('filtered-data', 'data'), Input('language-store', 'data'),
         Input('main-tabs', 'value')],
    )
    def update_overview_charts(data, language, active_tab):
        if active_tab != 'tab-overview':
            raise dash.exceptions.PreventUpdate
        empty = go.Figure()
        empty.update_layout(plot_bgcolor=COLORS['background'],
                            paper_bgcolor=COLORS['card'], font_color=COLORS['text'])
        if not data or not isinstance(data, dict):
            return empty, empty, empty
        dff = _apply_filter(df, data)
        lang_system.set_language(language)

        hcol = 'health_status_de' if language == 'de' else 'health_status_en'
        rcol = 'risk_level_de'    if language == 'de' else 'risk_level_en'

        # Health histogram
        if hcol in dff.columns:
            health_fig = px.histogram(
                dff, x='health_score', color=hcol,
                title=lang_system.get_text('health_distribution'),
                color_discrete_map={
                    'Excellent': COLORS['success'], 'Good': '#8BC34A',
                    'Fair': COLORS['warning'],       'Poor': COLORS['danger'],
                    'Ausgezeichnet': COLORS['success'], 'Gut': '#8BC34A',
                    'Akzeptabel': COLORS['warning'],     'Schlecht': COLORS['danger'],
                },
            )
        else:
            health_fig = empty

        # Risk pie
        if rcol in dff.columns:
            rc = dff[rcol].value_counts()
            risk_fig = px.pie(
                values=rc.values, names=rc.index,
                title=lang_system.get_text('risk_distribution'),
                color_discrete_sequence=[COLORS['danger'], COLORS['warning'],
                                         COLORS['success'], COLORS['primary']],
            )
        else:
            risk_fig = empty

        # Failure probability heatmap — Machine × Time
        if all(c in dff.columns for c in ['machine_id', 'timestamp', 'failure_prob']):
            dff['timestamp']   = pd.to_datetime(dff['timestamp'])
            dff['hour_bucket'] = dff['timestamp'].dt.floor('12H')  # 12H buckets = fewer columns
            top_machines       = (dff.groupby('machine_id')['failure_prob']
                                     .mean().sort_values(ascending=False)
                                     .head(20).index.tolist())  # 20 machines max
            pivot = (dff[dff['machine_id'].isin(top_machines)]
                     .groupby(['machine_id', 'hour_bucket'])['failure_prob']
                     .mean().unstack(fill_value=0))
            pivot = pivot.loc[top_machines]
            col_labels = [c.strftime('%d %b %H:%M') for c in pivot.columns]
            colorscale = [
                [0.00, '#0E0F11'], [0.15, '#1a1200'],
                [0.35, '#7A5010'], [0.55, '#F5A623'],
                [0.75, '#E05A00'], [1.00, '#EF4444'],
            ]
            heatmap_fig = go.Figure(go.Heatmap(
                z=pivot.values * 100,
                x=col_labels, y=pivot.index.tolist(),
                colorscale=colorscale, zmin=0, zmax=100,
                hoverongaps=False,
                hovertemplate=(
                    '<b>%{y}</b><br>Window: %{x}<br>'
                    'Failure Probability: <b>%{z:.1f}%</b><extra></extra>'
                ),
                colorbar=dict(
                    title=dict(text='Fail. Prob. %',
                               font=dict(size=11, color=COLORS['muted'])),
                    tickfont=dict(size=10, color=COLORS['muted']), ticksuffix='%',
                    bgcolor=COLORS['card'], bordercolor=COLORS['border'],
                    borderwidth=1, thickness=12, len=0.9,
                ),
                xgap=1, ygap=1,
            ))
            heatmap_fig.update_layout(
                title=dict(
                    text='Failure Probability — Machine × Time Window',
                    font=dict(size=16, color=COLORS['text']),
                    x=0, xanchor='left', pad=dict(l=4),
                ),
                plot_bgcolor=COLORS['background'], paper_bgcolor=COLORS['card'],
                font=dict(color=COLORS['text']),
                xaxis=dict(tickfont=dict(size=10, color=COLORS['muted']),
                           showgrid=False, tickangle=-35),
                yaxis=dict(tickfont=dict(size=10, color=COLORS['muted']),
                           autorange='reversed', showgrid=False),
                margin=dict(l=90, r=120, t=50, b=60),
            )
        else:
            heatmap_fig = empty

        for fig in (health_fig, risk_fig):
            fig.update_layout(plot_bgcolor=COLORS['background'],
                              paper_bgcolor=COLORS['card'], font_color=COLORS['text'])
        return health_fig, risk_fig, heatmap_fig

    # ── Sensor + predictive charts ────────────────────────────────────────────
    @app.callback(
        [Output('sensor_trend', 'figure'),
         Output('vibration_3d', 'figure'),
         Output('failure_probability', 'figure'),
         Output('rul_estimation', 'figure'),
         Output('feature_importance', 'figure')],
        [Input('filtered-data', 'data'), Input('language-store', 'data'),
         Input('main-tabs', 'value')],
    )
    def update_advanced_charts(data, language, active_tab):
        if active_tab not in ('tab-sensor', 'tab-predictive'):
            raise dash.exceptions.PreventUpdate
        empty = go.Figure()
        empty.update_layout(plot_bgcolor=COLORS['card'],
                            paper_bgcolor=COLORS['card'], font_color=COLORS['text'])
        if not data or not isinstance(data, dict):
            return empty, empty, empty, empty, empty
        dff = _apply_filter(df, data)
        lang_system.set_language(language)
        T = lang_system.get_text

        # Sample down to ~500 rows for all time-series charts (prevents browser freeze)
        step = max(1, len(dff) // 500)
        plot_df = dff.sort_values('timestamp').iloc[::step]

        # Sensor trend (3-subplot) — sampled
        sensor_fig = make_subplots(rows=3, cols=1,
            subplot_titles=[T('temperature_trends'), T('power_vibration'), T('tool_wear')],
            vertical_spacing=0.1)
        if all(c in plot_df.columns for c in ['timestamp', 'air_temp', 'process_temp']):
            sensor_fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['air_temp'],
                                            name='Air Temp', line=dict(color=COLORS['primary'])), row=1, col=1)
            sensor_fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['process_temp'],
                                            name='Process Temp', line=dict(color=COLORS['danger'])), row=1, col=1)
        if all(c in plot_df.columns for c in ['timestamp', 'power_consumption', 'vibration_magnitude']):
            sensor_fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['power_consumption'],
                                            name='Power', line=dict(color=COLORS['email'])), row=2, col=1)
            sensor_fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['vibration_magnitude'],
                                            name='Vibration', line=dict(color=COLORS['warning'])), row=2, col=1)
        if all(c in plot_df.columns for c in ['timestamp', 'tool_wear']):
            sensor_fig.add_trace(go.Scatter(x=plot_df['timestamp'], y=plot_df['tool_wear'],
                                            name='Tool Wear', line=dict(color=COLORS['success'])), row=3, col=1)
        sensor_fig.update_layout(height=600, plot_bgcolor=COLORS['card'],
                                  paper_bgcolor=COLORS['card'], font_color=COLORS['text'])

        # 3D vibration scatter — max 200 random points
        if all(c in dff.columns for c in ['vibration_x', 'vibration_y', 'vibration_z', 'machine_id']):
            vib_sample = dff.sample(min(200, len(dff)), random_state=42)
            vib_fig = px.scatter_3d(vib_sample, x='vibration_x', y='vibration_y', z='vibration_z',
                                    color='machine_id', title=T('vibration_analysis'), opacity=0.7)
        else:
            vib_fig = empty

        # Failure probability over time — TOP 8 machines only
        # Previously plotted ALL machines as individual lines = browser crash on 10k rows
        if all(c in dff.columns for c in ['timestamp', 'failure_prob', 'machine_id']):
            top8 = (dff.groupby('machine_id')['failure_prob']
                       .mean()
                       .sort_values(ascending=False)
                       .head(8)
                       .index.tolist())
            fail_df = dff[dff['machine_id'].isin(top8)].sort_values('timestamp')
            fail_df = (fail_df.groupby('machine_id', group_keys=False)
                               .apply(lambda g: g.iloc[::max(1, len(g) // 60)]))
            fail_fig = px.line(
                fail_df, x='timestamp', y='failure_prob', color='machine_id',
                title=T('failure_probability') + " — Top 8 Highest Risk",
                labels={'failure_prob': 'Failure Probability', 'timestamp': ''},
            )
            fail_fig.update_layout(yaxis=dict(tickformat='.0%', range=[0, 1]))
        else:
            fail_fig = empty

        # RUL bar chart — one row per machine, worst 20
        if all(c in dff.columns for c in ['estimated_rul_hours', 'machine_id']):
            rul_df = (dff.sort_values('estimated_rul_hours')
                        .drop_duplicates('machine_id')
                        .head(20))
            rul_fig = px.bar(rul_df, x='estimated_rul_hours', y='machine_id',
                             orientation='h', title=T('rul_estimation'),
                             color='estimated_rul_hours', color_continuous_scale='RdYlGn_r',
                             labels={'estimated_rul_hours': 'RUL (hours)', 'machine_id': ''})
        else:
            rul_fig = empty

        # Feature importance
        if analytics.models.get('failure_model') and analytics.models.get('features'):
            imp_df = pd.DataFrame({
                'feature':    analytics.models['features'],
                'importance': analytics.models['failure_model'].feature_importances_,
            }).sort_values('importance')
            feat_fig = px.bar(imp_df, x='importance', y='feature', orientation='h',
                              title=T('feature_importance'), color='importance',
                              color_continuous_scale='Viridis',
                              labels={'importance': 'Importance', 'feature': ''})
        else:
            feat_fig = empty

        for fig in (vib_fig, fail_fig, rul_fig, feat_fig):
            fig.update_layout(plot_bgcolor=COLORS['card'],
                              paper_bgcolor=COLORS['card'], font_color=COLORS['text'])
        return sensor_fig, vib_fig, fail_fig, rul_fig, feat_fig


# ── Private helpers ───────────────────────────────────────────────────────────

def _extract_machine_data(dff: pd.DataFrame, machine_id: str | None) -> dict:
    """Return a dict of sensor values for the selected machine (or first row)."""
    NUMERIC_COLS = [
        'machine_id', 'tool_wear', 'vibration_magnitude', 'temp_differential',
        'power_consumption', 'health_score', 'failure_prob', 'is_anomaly',
        'machine_type', 'timestamp', 'air_temp', 'process_temp', 'rot_speed', 'torque',
    ]
    data: dict = {}
    if machine_id:
        mdf = dff[dff['machine_id'] == machine_id]
        if not mdf.empty:
            row = mdf.sort_values('timestamp', ascending=False).iloc[0]
            for k in NUMERIC_COLS:
                if k not in row.index:
                    continue
                v = row[k]
                if isinstance(v, (int, float, np.integer, np.floating)):
                    data[k] = float(v)
                elif k == 'is_anomaly':
                    data[k] = bool(v)
                elif k == 'timestamp':
                    data[k] = v.strftime('%Y-%m-%d %H:%M:%S') if hasattr(v, 'strftime') else str(v)
                else:
                    data[k] = str(v)
            data['risk_level']          = str(row.get('risk_level_en', 'Unknown'))
            data['maintenance_urgency'] = str(row.get('maintenance_urgency_en', 'Monitor'))
    elif len(dff) > 0:
        row = dff.iloc[0]
        for k in ['machine_id', 'health_score', 'failure_prob', 'machine_type',
                  'tool_wear', 'vibration_magnitude', 'temp_differential', 'power_consumption']:
            if k in row.index:
                v = row[k]
                data[k] = bool(v) if k == 'is_anomaly' else (float(v) if isinstance(v, (int, float, np.integer, np.floating)) else str(v))
        data['is_anomaly'] = bool(row.get('is_anomaly', False))
    return data