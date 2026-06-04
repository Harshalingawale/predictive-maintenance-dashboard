
# Machine schematic image generator (PIL-based)

import base64
import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from app.language import LanguageSystem


class MachinePartDefinition:
    """Describes a single rendered part on a machine schematic."""

    def __init__(self, name: str, display_name: str, machine_type: str,
                 x: int, y: int, width: int, height: int,
                 normal_color: str = "#4CAF50",
                 warning_color: str = "#FF9800",
                 critical_color: str = "#F44336"):
        self.name          = name
        self.display_name  = display_name
        self.machine_type  = machine_type
        self.x, self.y     = x, y
        self.width, self.height = width, height
        self.normal_color  = normal_color
        self.warning_color = warning_color
        self.critical_color = critical_color
        self.status        = "normal"

    def color_for_status(self, status: str) -> str:
        return {
            'critical': self.critical_color,
            'warning':  self.warning_color,
        }.get(status, self.normal_color)


class VisualDiagnosticsSystem:
    """
    Generates PIL-based machine schematic images with color-coded
    component health and returns them as base64 PNG strings.
    """

    # Part definitions for each machine archetype
    _CNC_PARTS = [
        MachinePartDefinition("spindle",        "Spindle Assembly", "CNC", 300, 150, 100, 80),
        MachinePartDefinition("tool_changer",   "Tool Changer",     "CNC", 450, 100, 120, 60),
        MachinePartDefinition("coolant_system", "Coolant System",   "CNC", 150, 300, 120, 80),
        MachinePartDefinition("ball_screw",     "Ball Screw",       "CNC", 100, 200, 400, 20),
        MachinePartDefinition("linear_guides",  "Linear Guides",    "CNC", 100, 250, 400, 15),
        MachinePartDefinition("controller",     "Controller",       "CNC", 550, 300, 100, 80),
        MachinePartDefinition("power_supply",   "Power Supply",     "CNC",  50, 350,  80, 60),
    ]
    _REP_PARTS = [
        MachinePartDefinition("gripper",    "Gripper Assembly", "REP", 400,  50,  80, 60),
        MachinePartDefinition("joint_1",    "Robot Joint 1",    "REP", 200, 100,  60, 60),
        MachinePartDefinition("joint_2",    "Robot Joint 2",    "REP", 300, 150,  60, 60),
        MachinePartDefinition("joint_3",    "Robot Joint 3",    "REP", 400, 200,  60, 60),
        MachinePartDefinition("controller", "Controller",       "REP", 550, 250, 100, 80),
        MachinePartDefinition("power_supply","Power Supply",    "REP",  50, 300,  80, 60),
    ]

    def __init__(self, language_system: Optional[LanguageSystem] = None):
        self.lang = language_system or LanguageSystem('en')
        self._definitions: dict[str, list[MachinePartDefinition]] = {
            'CNC': self._CNC_PARTS,
            'REP': self._REP_PARTS,
            'M':   self._CNC_PARTS,
            'L':   self._REP_PARTS,
            'H':   self._CNC_PARTS,
        }
        # Flat part registry for quick lookup by name
        self._parts: dict[str, MachinePartDefinition] = {
            p.name: p
            for parts in self._definitions.values()
            for p in parts
        }

    def set_language(self, lang: str):
        self.lang.set_language(lang)

    # ------------------------------------------------------------------
    def generate_machine_image(
        self, machine_type: str,
        status_data: Optional[dict] = None,
        machine_id: str = "",
        health_score: float = 100.0,
        failure_prob: float = 0.0,
    ) -> str:
        """Return a base64-encoded PNG of the machine schematic."""
        img  = Image.new('RGB', (800, 600), color='#16181D')
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        parts = self._definitions.get(
            machine_type if machine_type in self._definitions else 'CNC', []
        )

        # Outer chassis
        draw.rectangle([50, 100, 750, 400], outline='#666666', width=3)

        # Parts
        for part in parts:
            status = (status_data or {}).get(part.name, 'normal')
            color  = part.color_for_status(status)
            draw.rectangle(
                [part.x, part.y, part.x + part.width, part.y + part.height],
                outline=color, width=3,
            )
            draw.text((part.x + 5, part.y - 15), part.display_name,
                      fill='#FFFFFF', font=font)

        # Title
        title = f"{machine_type} — {machine_id}" if machine_id else f"{machine_type} Machine"
        draw.text((300, 20), title, fill='#FFFFFF', font=font)

        # Health & failure prob readout
        health_color = '#34D399' if health_score >= 60 else ('#FBBF24' if health_score >= 40 else '#F87171')
        fail_color   = '#34D399' if failure_prob <= 0.3  else ('#FBBF24' if failure_prob <= 0.6  else '#F87171')
        draw.text((50, 450), f"Health: {health_score:.1f}",     fill=health_color, font=font)
        draw.text((50, 470), f"Failure Prob: {failure_prob:.1%}", fill=fail_color, font=font)

        # Legend
        for x, color, label_key in [
            (50,  '#34D399', 'normal'),
            (200, '#FBBF24', 'warning'),
            (350, '#F87171', 'critical'),
        ]:
            draw.rectangle([x, 510, x + 30, 530], fill=color)
            draw.text([x + 35, 512], self.lang.get_text(label_key),
                      fill='#FFFFFF', font=font)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    # ------------------------------------------------------------------
    def analyze_machine_data(self, machine_data: dict) -> dict[str, str]:
        """
        Map raw sensor values to per-part status strings
        ('normal' | 'warning' | 'critical').
        """
        status: dict[str, str] = {}

        tw = machine_data.get('tool_wear', 0)
        if tw > 250:
            status['spindle'] = 'critical'; status['tool_changer'] = 'warning'
        elif tw > 200:
            status['spindle'] = 'warning';  status['tool_changer'] = 'warning'

        vib = machine_data.get('vibration_magnitude', 0)
        bearing_parts = ['ball_screw', 'linear_guides', 'joint_1', 'joint_2', 'joint_3']
        if vib > 10:
            for p in bearing_parts: status[p] = 'critical'
        elif vib > 5:
            for p in bearing_parts: status[p] = 'warning'

        td = machine_data.get('temp_differential', 0)
        if td > 20:   status['coolant_system'] = 'critical'
        elif td > 10: status['coolant_system'] = 'warning'

        pc = machine_data.get('power_consumption', 0)
        if pc > 8:
            status['power_supply'] = 'critical'; status['controller'] = 'critical'
        elif pc > 6:
            status['power_supply'] = 'warning';  status['controller'] = 'warning'

        if machine_data.get('is_anomaly', False):
            for name in self._parts:
                status.setdefault(name, 'warning')

        hs = machine_data.get('health_score', 100)
        if hs < 40:
            for name in self._parts: status[name] = 'critical'
        elif hs < 60:
            for name in ['spindle', 'ball_screw', 'power_supply',
                         'controller', 'gripper', 'joint_1']:
                status.setdefault(name, 'warning')

        return status
