import json
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import pandas as pd

from app.language import LanguageSystem


# Email Alert System

class EmailAlertSystem:
    """
    Handles SMTP email delivery for maintenance alerts.
    Config is loaded from / written to email_config.json.
    """

    DEFAULT_CONFIG = {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "your-email@gmail.com",
        "sender_password": "your-app-password",
        "receiver_emails": ["maintenance-team@company.com"],
        "cc_emails": [],
        "bcc_emails": [],
        "alert_cooldown_minutes": 30,
        "enable_ssl": True,
        "enable_tls": True,
        "email_template": {
            "subject_prefix": "[BRUSS Alert] ",
            "company_name": "BRUSS Manufacturing",
            "footer": "This is an automated alert from BRUSS Predictive Maintenance System.",
        },
        "language": "en",
    }

    def __init__(self, config_path: str = "email_config.json",
                 language_system: Optional[LanguageSystem] = None):
        self.config        = self._load_config(config_path)
        self.alert_history: list = []
        self.last_sent_time: dict = {}
        self.lang          = language_system or LanguageSystem('en')

    # ------------------------------------------------------------------
    def _load_config(self, config_path: str) -> dict:
        config = dict(self.DEFAULT_CONFIG)
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    loaded = json.load(f)
                config.update(loaded)
                return config
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
        # Write default config so user knows what to fill in
        with open(config_path, 'w') as f:
            json.dump(self.DEFAULT_CONFIG, f, indent=4)
        return config

    def set_language(self, lang: str):
        self.config['language'] = lang
        self.lang.set_language(lang)

    # ------------------------------------------------------------------
    def send_email_alert(self, alert_data: dict, include_report: bool = False,
                         df_snapshot: Optional[pd.DataFrame] = None) -> bool:
        """Send a single HTML email alert. Respects cooldown per machine+severity."""
        self.set_language(self.config.get('language', 'en'))
        alert_key = f"{alert_data.get('machine_id', 'global')}_{alert_data.get('severity', 'unknown')}"
        now = datetime.now()

        # Cooldown check
        if alert_key in self.last_sent_time:
            elapsed = (now - self.last_sent_time[alert_key]).total_seconds() / 60
            if elapsed < self.config['alert_cooldown_minutes']:
                print(self.lang.get_text('alert_cooldown', alert_key, elapsed))
                return False

        try:
            msg = self._build_message(alert_data)

            if include_report and df_snapshot is not None:
                csv_bytes = df_snapshot.to_csv(index=False).encode('utf-8')
                attachment = MIMEApplication(csv_bytes, Name='machine_report.csv')
                attachment['Content-Disposition'] = (
                    f'attachment; filename="machine_report_{now.strftime("%Y%m%d_%H%M")}.csv"'
                )
                msg.attach(attachment)

            with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                if self.config['enable_tls']:
                    server.starttls()
                if self.config['sender_password']:
                    server.login(self.config['sender_email'], self.config['sender_password'])
                server.send_message(msg)

            self.alert_history.append({
                'timestamp':  now,
                'alert_key':  alert_key,
                'severity':   alert_data['severity'],
                'machine_id': alert_data.get('machine_id', 'N/A'),
                'sent_to':    self.config['receiver_emails'],
                'subject':    msg['Subject'],
                'language':   self.config['language'],
            })
            self.last_sent_time[alert_key] = now
            print(self.lang.get_text('email_sent', alert_data['severity'], alert_data['title']))
            return True

        except (smtplib.SMTPConnectError, ConnectionRefusedError,
                TimeoutError, smtplib.SMTPServerDisconnected):
            print(self.lang.get_text('network_unreachable'))
            return False
        except smtplib.SMTPAuthenticationError:
            print(self.lang.get_text('auth_failed'))
            return False
        except Exception as e:
            print(self.lang.get_text('failed_send', type(e).__name__))
            return False

    # ------------------------------------------------------------------
    def _build_message(self, alert_data: dict) -> MIMEMultipart:
        msg = MIMEMultipart()
        msg['From']    = self.config['sender_email']
        msg['To']      = ', '.join(self.config['receiver_emails'])
        if self.config['cc_emails']:
            msg['Cc']  = ', '.join(self.config['cc_emails'])
        prefix         = self.config['email_template']['subject_prefix']
        msg['Subject'] = f"{prefix}{alert_data['severity']}: {alert_data['title']}"
        msg.attach(MIMEText(self._create_html_email(alert_data), 'html'))
        return msg

    def _create_html_email(self, alert_data: dict) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        severity_colors = {
            'CRITICAL': '#dc3545', 'HIGH': '#fd7e14',
            'MEDIUM': '#ffc107', 'LOW': '#28a745', 'INFO': '#17a2b8',
        }
        color = severity_colors.get(alert_data.get('severity', 'INFO'), '#6c757d')
        metrics_html = "".join(
            f'<div class="metric-card">'
            f'<strong>{k}:</strong><br>'
            f'<span style="font-size:18px;font-weight:bold;">{v}</span>'
            f'</div>'
            for k, v in alert_data.get('metrics', {}).items()
        )
        return f"""<!DOCTYPE html><html><head><style>
            body{{font-family:Arial,sans-serif;line-height:1.6;color:#333}}
            .container{{max-width:600px;margin:0 auto;padding:20px;
                        border:1px solid #ddd;border-radius:5px}}
            .header{{background-color:{color};color:white;padding:15px;
                     border-radius:5px 5px 0 0}}
            .content{{padding:20px;background-color:#f9f9f9}}
            .metrics{{display:grid;grid-template-columns:repeat(2,1fr);
                       gap:10px;margin:20px 0}}
            .metric-card{{background:white;padding:15px;border-radius:5px;
                           border-left:4px solid {color}}}
            .footer{{margin-top:20px;padding-top:20px;border-top:1px solid #ddd;
                     font-size:12px;color:#666}}
            .button{{display:inline-block;padding:10px 20px;
                     background-color:{color};color:white;
                     text-decoration:none;border-radius:3px}}
        </style></head><body><div class="container">
            <div class="header">
                <h2>BRUSS Predictive Maintenance</h2>
                <p>{timestamp}</p>
            </div>
            <div class="content">
                <h3>{alert_data.get('title', 'Alert')}</h3>
                <p><strong>Machine:</strong> {alert_data.get('machine_id', 'N/A')}</p>
                <p><strong>Message:</strong> {alert_data.get('message', '')}</p>
                <div class="metrics">{metrics_html}</div>
                <a href="http://localhost:8050" class="button">Go to Dashboard</a>
            </div>
            <div class="footer">
                <p>Automated message from BRUSS Predictive Maintenance System</p>
            </div>
        </div></body></html>"""

    # ------------------------------------------------------------------
    def get_alert_stats(self, hours: int = 24) -> dict:
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [a for a in self.alert_history if a['timestamp'] > cutoff]
        return {
            'total_alerts':  len(recent),
            'by_severity':   {
                sev: sum(1 for a in recent if a['severity'] == sev)
                for sev in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')
            },
            'last_alert': max((a['timestamp'] for a in recent), default=None),
        }


# Alert Engine

class AlertEngine:
    """
    Evaluates machine rows and produces structured alert records.
    Optionally wires into EmailAlertSystem.
    """

    def __init__(self, email_system: Optional[EmailAlertSystem] = None,
                 language_system: Optional[LanguageSystem] = None,
                 auto_send_emails: bool = False):
        self.alerts:           list  = []
        self.email_system            = email_system
        self.alert_counter:    int   = 0
        self.auto_send_emails        = auto_send_emails
        self.lang                    = language_system or LanguageSystem('en')

    def set_language(self, lang: str):
        self.lang.set_language(lang)
        if self.email_system:
            self.email_system.set_language(lang)

    # ------------------------------------------------------------------
    def evaluate(self, row: pd.Series) -> list:
        """Evaluate one machine row; return list of alert dicts triggered."""
        triggered = []

        if row.get('failure_prob', 0) > 0.7:
            triggered.append(self._make_alert(
                'CRITICAL', 'high_failure_alert', 'critical_failure_prob',
                [row['machine_id'], row['failure_prob']], row,
                {'failure_prob': row['failure_prob'],
                 'health_score': row.get('health_score', 0)},
            ))

        if row.get('health_score', 100) < 40:
            triggered.append(self._make_alert(
                'HIGH', 'low_health_alert', 'critically_low_health',
                [row['machine_id'], row['health_score']], row,
                {'health_score': row.get('health_score', 0)},
            ))

        if row.get('is_anomaly', False):
            triggered.append(self._make_alert(
                'MEDIUM', 'anomaly_detected', 'unusual_behavior',
                [row['machine_id']], row,
                {'vibration': row.get('vibration_magnitude', 0)},
            ))

        if row.get('tool_wear', 0) > 200:
            triggered.append(self._make_alert(
                'MEDIUM', 'high_tool_wear', 'tool_wear_high',
                [row['machine_id'], row['tool_wear']], row,
                {'tool_wear': row['tool_wear']},
            ))

        self.alerts.extend(triggered)
        return triggered

    # ------------------------------------------------------------------
    def _make_alert(self, severity: str, title_key: str, message_key: str,
                    message_params: list, row: pd.Series, metrics: dict) -> dict:
        self.alert_counter += 1
        return {
            'alert_id':      f"ALERT_{self.alert_counter:06d}",
            'severity':      severity,
            'title_key':     title_key,
            'message_key':   message_key,
            'message_params': message_params,
            'machine_id':    row['machine_id'],
            'timestamp':     datetime.now(),
            'metrics':       metrics,
        }

    def _alert_to_email_dict(self, alert: dict) -> dict:
        title   = self.lang.get_text(alert.get('title_key', ''))
        message = self.lang.get_text(
            alert.get('message_key', ''), *alert.get('message_params', [])
        )
        translated_metrics = {}
        for key, value in alert.get('metrics', {}).items():
            t_key = self.lang.get_text(key.lower().replace(' ', '_'))
            formatted = (
                f"{value:.1%}" if 'prob' in key
                else f"{value:.2f}" if isinstance(value, float)
                else str(value)
            )
            translated_metrics[t_key] = formatted
        return {
            'severity':  alert['severity'],
            'title':     title,
            'message':   message,
            'machine_id': alert.get('machine_id', 'N/A'),
            'metrics':   translated_metrics,
            'alert_id':  alert.get('alert_id', 'N/A'),
        }

    # ------------------------------------------------------------------
    def get_recent_alerts(self, limit: int = 15) -> list:
        return sorted(self.alerts, key=lambda x: x['timestamp'], reverse=True)[:limit]

    def get_alert_summary(self) -> dict:
        return {
            'total':    len(self.alerts),
            'critical': sum(1 for a in self.alerts if a['severity'] == 'CRITICAL'),
            'high':     sum(1 for a in self.alerts if a['severity'] == 'HIGH'),
            'medium':   sum(1 for a in self.alerts if a['severity'] == 'MEDIUM'),
            'last_alert': self.alerts[-1]['timestamp'] if self.alerts else None,
        }

    # ------------------------------------------------------------------
    def send_daily_report(self, email_system: EmailAlertSystem,
                          df: pd.DataFrame):
        today        = datetime.now().date()
        today_alerts = [a for a in self.alerts if a['timestamp'].date() == today]
        report_data  = {
            'severity':   'INFO',
            'title':      self.lang.get_text('daily_report_title', today.strftime("%B %d, %Y")),
            'message':    self.lang.get_text('daily_report_message', today.strftime("%B %d, %Y")),
            'machine_id': 'SYSTEM',
            'metrics': {
                'total_machines':        df['machine_id'].nunique(),
                'today_alerts':          len(today_alerts),
                'critical_alerts_today': sum(1 for a in today_alerts if a['severity'] == 'CRITICAL'),
                'avg_health_score':      (
                    f"{df['health_score'].mean():.1f}"
                    if 'health_score' in df.columns else 'N/A'
                ),
            },
        }
        email_system.send_email_alert(
            self._alert_to_email_dict(report_data),
            include_report=True, df_snapshot=df,
        )

    def send_critical_alerts(self, email_system: EmailAlertSystem) -> dict:
        critical = [a for a in self.alerts if a['severity'] in ('CRITICAL', 'HIGH')]
        if not critical:
            return {'sent': 0, 'failed': 0}
        summary = {
            'severity':   'CRITICAL',
            'title':      self.lang.get_text('critical_summary_title', len(critical)),
            'message':    self.lang.get_text('critical_summary_message', len(critical)),
            'machine_id': 'MULTIPLE',
            'metrics': {
                'total_alerts': len(critical),
                'critical':     sum(1 for a in critical if a['severity'] == 'CRITICAL'),
            },
            'alert_id': f"SUMMARY-{datetime.now().strftime('%Y%m%d%H%M')}",
        }
        success = email_system.send_email_alert(self._alert_to_email_dict(summary))
        return ({'sent': len(critical), 'failed': 0}
                if success else {'sent': 0, 'failed': len(critical)})
