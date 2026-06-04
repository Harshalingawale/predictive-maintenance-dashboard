
# Shift Handover PDF Generator & Auto-Scheduler

import base64
import os
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import pandas as pd
import schedule
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.language import LanguageSystem


class ShiftHandoverReportGenerator:
    """
    Generates a professional A4 PDF shift handover report.

    Shifts:
      - Morning   06:00 – 14:00
      - Afternoon 14:00 – 22:00
      - Night     22:00 – 06:00 (spans two calendar days)
    """

    SHIFT_DEFINITIONS = {
        'morning':   {'label': 'Morning Shift',   'label_de': 'Frühschicht',  'start': 6,  'end': 14},
        'afternoon': {'label': 'Afternoon Shift', 'label_de': 'Spätschicht', 'start': 14, 'end': 22},
        'night':     {'label': 'Night Shift',     'label_de': 'Nachtschicht','start': 22, 'end':  6},
    }

    def __init__(self, language_system: Optional[LanguageSystem] = None):
        self.lang                 = language_system or LanguageSystem('en')
        self.last_report_path:    Optional[str]      = None
        self.last_report_time:    Optional[datetime] = None
        self.auto_schedule_active: bool              = False
        self._scheduler_thread:   Optional[threading.Thread] = None
        os.makedirs("shift_reports", exist_ok=True)

    def set_language(self, lang: str):
        self.lang.set_language(lang)

    # Shift helpers

    def get_current_shift(self) -> str:
        hour = datetime.now().hour
        if 6 <= hour < 14:   return 'morning'
        if 14 <= hour < 22:  return 'afternoon'
        return 'night'

    def get_shift_time_range(self, shift_key: str,
                             reference_date: Optional[datetime] = None) -> tuple:
        if reference_date is None:
            reference_date = datetime.now()
        shift = self.SHIFT_DEFINITIONS[shift_key]
        today = reference_date.date()
        if shift_key == 'night':
            start_dt = datetime.combine(today - timedelta(days=1),
                                        datetime.min.time()).replace(hour=22)
            end_dt   = datetime.combine(today, datetime.min.time()).replace(hour=6)
        else:
            start_dt = datetime.combine(today, datetime.min.time()).replace(hour=shift['start'])
            end_dt   = datetime.combine(today, datetime.min.time()).replace(hour=shift['end'])
        return start_dt, end_dt

    # PDF generation

    def generate_pdf(self, df: pd.DataFrame, alert_engine,
                     shift_key: Optional[str] = None,
                     output_path: Optional[str] = None) -> str:
        """Build and save the shift handover PDF. Returns file path."""
        if shift_key is None:
            shift_key = self.get_current_shift()

        shift_info = self.SHIFT_DEFINITIONS[shift_key]
        now        = datetime.now()
        shift_start, shift_end = self.get_shift_time_range(shift_key)

        fname = output_path or (
            f"shift_reports/BRUSS_ShiftReport_{shift_key}_{now.strftime('%Y%m%d_%H%M')}.pdf"
        )

        # ── Filter data to shift window 
        dff = df.copy()
        if 'timestamp' in dff.columns:
            mask = (dff['timestamp'] >= shift_start) & (dff['timestamp'] <= shift_end)
            shift_df = dff[mask] if mask.sum() >= 10 else dff.tail(500)
        else:
            shift_df = dff.tail(500)

        shift_alerts = [
            a for a in alert_engine.alerts
            if shift_start <= a['timestamp'] <= shift_end
        ] or alert_engine.alerts[-20:]

        # ── KPIs 
        total_machines    = shift_df['machine_id'].nunique() if 'machine_id' in shift_df.columns else 0
        avg_health        = shift_df['health_score'].mean()  if 'health_score' in shift_df.columns else 0
        critical_count    = sum(1 for a in shift_alerts if a.get('severity') == 'CRITICAL')
        high_count        = sum(1 for a in shift_alerts if a.get('severity') == 'HIGH')
        immediate_machines = (
            shift_df[shift_df['maintenance_urgency_en'] == 'Immediate']['machine_id'].nunique()
            if 'maintenance_urgency_en' in shift_df.columns else 0
        )
        anomaly_count = int(shift_df['is_anomaly'].sum()) if 'is_anomaly' in shift_df.columns else 0

        top_machines = (
            shift_df.sort_values('failure_prob', ascending=False)
            .drop_duplicates('machine_id').head(10)
            if 'failure_prob' in shift_df.columns
            else shift_df.head(10)
        )

        # ── Build document 
        doc   = SimpleDocTemplate(fname, pagesize=A4,
                                  rightMargin=15*mm, leftMargin=15*mm,
                                  topMargin=15*mm,  bottomMargin=15*mm)
        story = []
        st    = self._build_styles()

        # Header banner
        story.append(self._make_banner())
        story.append(Spacer(1, 8))

        # Title
        if self.lang.current_lang == 'de':
            title_text = f"Schichtübergabebericht — {shift_info['label_de']}"
        else:
            title_text = f"Shift Handover Report — {shift_info['label']}"
        story.append(Paragraph(title_text, st['title']))
        story.append(Paragraph(
            f"{shift_start.strftime('%d %B %Y  |  %H:%M')} – {shift_end.strftime('%H:%M')}  "
            f"|  Generated: {now.strftime('%d %b %Y %H:%M')}",
            st['subtitle']
        ))
        story.append(HRFlowable(width="100%", thickness=2,
                                color=colors.HexColor('#00BCD4'), spaceAfter=10))

        # KPI row
        kpi_health_color = (
            '#2E7D32' if avg_health >= 70
            else '#E65100' if avg_health >= 50
            else '#C62828'
        )
        kpis = [
            ("Total Machines",        total_machines,    '#1565C0'),
            ("Avg Health Score",      f"{avg_health:.1f}", kpi_health_color),
            ("Shift Alerts",          len(shift_alerts), '#E65100' if len(shift_alerts) > 5 else '#333333'),
            ("Critical Alerts",       critical_count,    '#C62828' if critical_count > 0 else '#2E7D32'),
            ("Need Immediate Action", immediate_machines,'#C62828' if immediate_machines > 0 else '#2E7D32'),
            ("Anomalies Detected",    anomaly_count,     '#7B1FA2' if anomaly_count > 0 else '#2E7D32'),
        ]
        story.append(self._make_kpi_table(kpis, st))
        story.append(Spacer(1, 12))

        # Sections
        story += self._section_summary(critical_count, immediate_machines,
                                       avg_health, anomaly_count, st)
        story.append(Paragraph("2. Top Machines Requiring Attention", st['section']))
        story.append(Spacer(1, 4))
        story.append(self._machine_table(top_machines, st) if len(top_machines) else
                     Paragraph("No machine data available.", st['body']))
        story.append(Spacer(1, 12))
        story += self._section_alerts(shift_alerts, critical_count, high_count, st)
        story += self._section_sensors(shift_df, st)
        story += self._section_checklist(st)
        story += self._section_signatures(now, st)

        # Footer
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor('#CFD8DC'), spaceAfter=4))
        story.append(Paragraph(
            f"BRUSS Predictive Maintenance System  |  "
            f"Auto-generated: {now.strftime('%d %b %Y %H:%M:%S')}  |  "
            f"Report ID: BRUSS-{shift_key.upper()}-{now.strftime('%Y%m%d%H%M')}  |  "
            f"Confidential — Internal Use Only",
            st['footer']
        ))

        doc.build(story)
        self.last_report_path = fname
        self.last_report_time = now
        print(f"✅ Shift handover report generated: {fname}")
        return fname


    # Section builders

    def _section_summary(self, critical_count, immediate_machines,
                         avg_health, anomaly_count, st) -> list:
        story = [Paragraph("1. Shift Summary", st['section']), Spacer(1, 4)]
        lines = []
        if critical_count > 0:
            lines.append(
                f"<font color='#C62828'><b>ATTENTION:</b></font> "
                f"{critical_count} CRITICAL alert(s) triggered. Immediate review required."
            )
        if immediate_machines > 0:
            lines.append(
                f"<b>{immediate_machines} machine(s)</b> require immediate maintenance. "
                "Communicate to incoming shift lead."
            )
        if avg_health < 60:
            lines.append(
                f"<font color='#E65100'><b>Fleet Health Warning:</b></font> "
                f"Avg health = {avg_health:.1f}/100 — below threshold of 60."
            )
        if anomaly_count > 0:
            lines.append(
                f"<b>{anomaly_count} anomalous reading(s)</b> detected by AI engine."
            )
        if not lines:
            lines.append(
                "<font color='#2E7D32'><b>Shift completed without critical events.</b></font> "
                "All machines within normal parameters."
            )
        for line in lines:
            story.append(Paragraph(line, st['body']))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 8))
        return story

    def _section_alerts(self, shift_alerts, critical_count, high_count, st) -> list:
        story = [Paragraph("3. Shift Alerts Log", st['section']), Spacer(1, 4)]
        if shift_alerts:
            story.append(Paragraph(
                f"Total alerts: <b>{len(shift_alerts)}</b>  |  "
                f"Critical: <b><font color='#C62828'>{critical_count}</font></b>  |  "
                f"High: <b><font color='#BF360C'>{high_count}</font></b>",
                st['body']
            ))
            story.append(Spacer(1, 4))
            story.append(self._alerts_table(shift_alerts, st))
        else:
            story.append(Paragraph(
                "<font color='#2E7D32'>No alerts triggered during this shift.</font>",
                st['body']
            ))
        story.append(Spacer(1, 12))
        return story

    def _section_sensors(self, shift_df: pd.DataFrame, st) -> list:
        story = [Paragraph("4. Sensor Statistics (Shift Average)", st['section']), Spacer(1, 4)]
        sensor_cols = {
            'air_temp': 'Air Temp (K)', 'process_temp': 'Process Temp (K)',
            'rot_speed': 'Rot. Speed (rpm)', 'torque': 'Torque (Nm)',
            'tool_wear': 'Tool Wear (min)', 'vibration_magnitude': 'Vibration Magnitude',
            'power_consumption': 'Power (kW)', 'temp_differential': 'Temp Differential (K)',
        }
        available = {k: v for k, v in sensor_cols.items() if k in shift_df.columns}
        if available:
            data = [['Sensor', 'Min', 'Mean', 'Max', 'Std Dev']]
            for col, label in available.items():
                s = shift_df[col]
                data.append([label, f"{s.min():.2f}", f"{s.mean():.2f}",
                              f"{s.max():.2f}", f"{s.std():.2f}"])
            tbl = Table(data, colWidths=[55*mm, 25*mm, 25*mm, 25*mm, 25*mm], repeatRows=1)
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#263238')),
                ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
                ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0, 0), (-1, 0), 9),
                ('FONTSIZE',   (0, 1), (-1, -1), 8),
                ('FONTNAME',   (0, 1), (-1, -1), 'Helvetica'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECEFF1')]),
                ('GRID',   (0, 0), (-1, -1), 0.5, colors.HexColor('#CFD8DC')),
                ('ALIGN',  (1, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING',    (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(tbl)
        else:
            story.append(Paragraph("Sensor data not available.", st['body']))
        story.append(Spacer(1, 12))
        return story

    def _section_checklist(self, st) -> list:
        items = [
            "Review all CRITICAL and HIGH alerts with incoming shift lead",
            "Confirm machines flagged as 'Immediate' have work orders in SAP",
            "Verify sensor calibration for machines with anomaly flags",
            "Update maintenance log for interventions performed this shift",
            "Confirm email notifications received by maintenance team",
            "Brief incoming shift on ongoing issues or observations",
            "Confirm next scheduled preventive maintenance tasks",
        ]
        data = [['', 'Task', 'Done']] + [[f"{i}.", item, '☐'] for i, item in enumerate(items, 1)]
        tbl  = Table(data, colWidths=[8*mm, 140*mm, 15*mm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#37474F')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('FONTNAME',   (0, 1), (-1, -1), 'Helvetica'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')]),
            ('GRID',   (0, 0), (-1, -1), 0.5, colors.HexColor('#B0BEC5')),
            ('ALIGN',  (0, 0), (0, -1), 'CENTER'),
            ('ALIGN',  (2, 0), (2, -1), 'CENTER'),
            ('FONTSIZE', (2, 1), (2, -1), 14),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return [Paragraph("5. Handover Checklist", st['section']),
                Spacer(1, 6), tbl, Spacer(1, 12)]

    def _section_signatures(self, now: datetime, st) -> list:
        data = [
            ['Outgoing Shift Lead:', '', 'Incoming Shift Lead:', ''],
            ['', '', '', ''],
            ['Name: ____________________', 'Sign: ____________________',
             'Name: ____________________', 'Sign: ____________________'],
            [f"Date/Time: {now.strftime('%d.%m.%Y  %H:%M')}", '',
             'Date/Time: ____________________', ''],
        ]
        tbl = Table(data, colWidths=[(A4[0]-30*mm)/4]*4)
        tbl.setStyle(TableStyle([
            ('FONTNAME',   (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE',   (0, 0), (-1, -1), 8),
            ('FONTNAME',   (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME',   (2, 0), (2, 0), 'Helvetica-Bold'),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return [Paragraph("6. Shift Handover Signatures", st['section']),
                Spacer(1, 8), tbl, Spacer(1, 16)]

    # Table builders

    def _make_banner(self) -> Table:
        st_left  = ParagraphStyle('BL', fontSize=10, textColor=colors.white,
                                  fontName='Helvetica-Bold', alignment=TA_LEFT)
        st_right = ParagraphStyle('BR', fontSize=9, textColor=colors.HexColor('#B3E5FC'),
                                  fontName='Helvetica', alignment=TA_RIGHT)
        data = [[Paragraph("BRUSS Manufacturing", st_left),
                 Paragraph("Predictive Maintenance System", st_right)]]
        tbl  = Table(data, colWidths=[(A4[0]-30*mm)*0.5]*2)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0D1B2A')),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return tbl

    def _make_kpi_table(self, kpis: list, styles: dict) -> Table:
        header_row, value_row = [], []
        for label, value, color_hex in kpis:
            header_row.append(Paragraph(label, styles['kpi_label']))
            val_style = ParagraphStyle(
                f'KV_{label}', parent=styles['kpi_value'],
                textColor=colors.HexColor(color_hex),
            )
            value_row.append(Paragraph(str(value), val_style))
        col_w = (A4[0] - 40*mm) / len(kpis)
        tbl   = Table([header_row, value_row], colWidths=[col_w]*len(kpis))
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F4F6F9')),
            ('BOX',        (0, 0), (-1, -1), 1, colors.HexColor('#DDE3EC')),
            ('INNERGRID',  (0, 0), (-1, -1), 0.5, colors.HexColor('#DDE3EC')),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return tbl

    def _machine_table(self, machines_df: pd.DataFrame, styles: dict) -> Table:
        headers = ['Machine ID', 'Type', 'Health Score', 'Failure Prob.',
                   'Risk Level', 'RUL (hrs)', 'Urgency']
        data = [headers]
        for _, row in machines_df.iterrows():
            data.append([
                str(row.get('machine_id', '')),
                str(row.get('machine_type', '')),
                f"{row.get('health_score', 0):.1f}",
                f"{row.get('failure_prob', 0):.1%}",
                str(row.get('risk_level_en', 'Unknown')),
                f"{row.get('estimated_rul_hours', 0):.0f}",
                str(row.get('maintenance_urgency_en', 'Monitor')),
            ])
        col_widths = [30*mm, 15*mm, 25*mm, 27*mm, 25*mm, 22*mm, 22*mm]
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3A5C')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 9),
            ('FONTSIZE',   (0, 1), (-1, -1), 8),
            ('FONTNAME',   (0, 1), (-1, -1), 'Helvetica'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F4F6F9')]),
            ('GRID',   (0, 0), (-1, -1), 0.5, colors.HexColor('#DDE3EC')),
            ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]
        for i, (_, row) in enumerate(machines_df.iterrows(), start=1):
            urgency = row.get('maintenance_urgency_en', 'Monitor')
            if urgency == 'Immediate':
                style_cmds += [
                    ('BACKGROUND', (6, i), (6, i), colors.HexColor('#FFEBEE')),
                    ('TEXTCOLOR',  (6, i), (6, i), colors.HexColor('#C62828')),
                    ('FONTNAME',   (6, i), (6, i), 'Helvetica-Bold'),
                ]
            elif urgency == 'Scheduled':
                style_cmds += [
                    ('BACKGROUND', (6, i), (6, i), colors.HexColor('#FFF8E1')),
                    ('TEXTCOLOR',  (6, i), (6, i), colors.HexColor('#E65100')),
                ]
        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    def _alerts_table(self, alerts: list, styles: dict) -> Table:
        data = [['Time', 'Machine ID', 'Severity', 'Description']]
        for alert in alerts[-30:]:
            msg = (
                self.lang.get_text(alert['message_key'], *alert.get('message_params', []))
                if 'message_key' in alert
                else alert.get('message', '')
            )
            data.append([
                alert['timestamp'].strftime('%H:%M:%S'),
                str(alert.get('machine_id', 'N/A')),
                str(alert.get('severity', 'INFO')),
                msg[:80] + ('...' if len(msg) > 80 else ''),
            ])
        tbl = Table(data, colWidths=[22*mm, 30*mm, 22*mm, None], repeatRows=1)
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1565C0')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 9),
            ('FONTSIZE',   (0, 1), (-1, -1), 8),
            ('FONTNAME',   (0, 1), (-1, -1), 'Helvetica'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#E3F2FD')]),
            ('GRID',   (0, 0), (-1, -1), 0.5, colors.HexColor('#DDE3EC')),
            ('ALIGN',  (0, 0), (2, -1), 'CENTER'),
            ('ALIGN',  (3, 1), (3, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        for i, alert in enumerate(alerts[-30:], start=1):
            sev = alert.get('severity', 'INFO')
            if sev == 'CRITICAL':
                style_cmds += [
                    ('BACKGROUND', (2, i), (2, i), colors.HexColor('#FFEBEE')),
                    ('TEXTCOLOR',  (2, i), (2, i), colors.HexColor('#C62828')),
                    ('FONTNAME',   (2, i), (2, i), 'Helvetica-Bold'),
                ]
            elif sev == 'HIGH':
                style_cmds += [
                    ('BACKGROUND', (2, i), (2, i), colors.HexColor('#FBE9E7')),
                    ('TEXTCOLOR',  (2, i), (2, i), colors.HexColor('#BF360C')),
                ]
            elif sev == 'MEDIUM':
                style_cmds.append(('TEXTCOLOR', (2, i), (2, i), colors.HexColor('#E65100')))
        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    # Style sheet

    def _build_styles(self) -> dict:
        base = getSampleStyleSheet()
        return {
            'title': ParagraphStyle(
                'ReportTitle', parent=base['Title'],
                fontSize=22, textColor=colors.HexColor('#1B3A5C'),
                spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold',
            ),
            'subtitle': ParagraphStyle(
                'ReportSubtitle', parent=base['Normal'],
                fontSize=11, textColor=colors.HexColor('#546E7A'),
                spaceAfter=4, alignment=TA_CENTER, fontName='Helvetica',
            ),
            'section': ParagraphStyle(
                'SectionHeader', parent=base['Heading1'],
                fontSize=13, textColor=colors.white,
                backColor=colors.HexColor('#1B3A5C'),
                spaceBefore=14, spaceAfter=6, leftIndent=8, fontName='Helvetica-Bold',
            ),
            'kpi_label': ParagraphStyle(
                'KpiLabel', parent=base['Normal'],
                fontSize=9, textColor=colors.HexColor('#546E7A'),
                alignment=TA_CENTER, fontName='Helvetica',
            ),
            'kpi_value': ParagraphStyle(
                'KpiValue', parent=base['Normal'],
                fontSize=20, textColor=colors.HexColor('#1B3A5C'),
                alignment=TA_CENTER, fontName='Helvetica-Bold',
            ),
            'body': ParagraphStyle(
                'ReportBody', parent=base['Normal'],
                fontSize=10, textColor=colors.HexColor('#333333'),
                spaceAfter=4, fontName='Helvetica',
            ),
            'footer': ParagraphStyle(
                'Footer', parent=base['Normal'],
                fontSize=8, textColor=colors.HexColor('#999999'),
                alignment=TA_CENTER, fontName='Helvetica',
            ),
        }

    # File utilities

    def get_pdf_as_base64(self, path: Optional[str] = None) -> Optional[str]:
        target = path or self.last_report_path
        if target and os.path.exists(target):
            with open(target, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        return None

    # Auto-scheduler

    def start_auto_scheduler(self, df: pd.DataFrame, alert_engine,
                             email_system=None):
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        self.auto_schedule_active = True

        def run():
            schedule.every().day.at("06:00").do(
                self._auto_generate, df, alert_engine, 'night', email_system)
            schedule.every().day.at("14:00").do(
                self._auto_generate, df, alert_engine, 'morning', email_system)
            schedule.every().day.at("22:00").do(
                self._auto_generate, df, alert_engine, 'afternoon', email_system)
            print("⏰ Shift report auto-scheduler started (6am / 2pm / 10pm)")
            while self.auto_schedule_active:
                schedule.run_pending()
                time.sleep(30)

        self._scheduler_thread = threading.Thread(target=run, daemon=True)
        self._scheduler_thread.start()

    def stop_auto_scheduler(self):
        self.auto_schedule_active = False
        schedule.clear()
        print("⏹️ Shift report auto-scheduler stopped")

    def _auto_generate(self, df: pd.DataFrame, alert_engine,
                       shift_key: str, email_system=None):
        try:
            path = self.generate_pdf(df, alert_engine, shift_key)
            if email_system:
                self._email_report(path, shift_key, email_system)
        except Exception as e:
            print(f"❌ Auto shift report failed: {e}")

    def _email_report(self, pdf_path: str, shift_key: str, email_system) -> bool:
        shift_label = self.SHIFT_DEFINITIONS[shift_key]['label']
        now         = datetime.now()
        try:
            msg = MIMEMultipart()
            msg['From']    = email_system.config['sender_email']
            msg['To']      = ', '.join(email_system.config['receiver_emails'])
            msg['Subject'] = (
                f"[BRUSS] Shift Handover Report — {shift_label} — "
                f"{now.strftime('%d %b %Y')}"
            )
            body = email_system._create_html_email({
                'severity':   'INFO',
                'title':      f"Shift Handover Report — {shift_label}",
                'message':    f"Please find attached the shift handover report for "
                              f"{shift_label} ({now.strftime('%d %B %Y')}).",
                'machine_id': 'SYSTEM',
                'metrics': {
                    'Shift':     shift_label,
                    'Generated': now.strftime('%H:%M:%S'),
                    'Date':      now.strftime('%d.%m.%Y'),
                },
            })
            msg.attach(MIMEText(body, 'html'))
            if os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    att = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
                    att['Content-Disposition'] = (
                        f'attachment; filename="{os.path.basename(pdf_path)}"'
                    )
                    msg.attach(att)
            with smtplib.SMTP(email_system.config['smtp_server'],
                              email_system.config['smtp_port']) as server:
                if email_system.config.get('enable_tls'):
                    server.starttls()
                if email_system.config.get('sender_password'):
                    server.login(email_system.config['sender_email'],
                                 email_system.config['sender_password'])
                server.send_message(msg)
            print(f"✅ Shift report emailed for {shift_label}")
            return True
        except Exception as e:
            print(f"❌ Failed to email shift report: {e}")
            return False
