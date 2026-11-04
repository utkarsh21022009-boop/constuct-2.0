"""Safety guardrails for industrial equipment troubleshooting.
Enforces the 4 core safety boundaries from FixPilot design:
1. No bypassing safety interlocks
2. No hazardous procedures without verified LOTO / zero-energy state
3. No live machinery controls in MVP
4. No unsupported guesses as facts
"""

import re
from typing import List, Tuple, Optional
from fixpilot.models import SafetyAssessment, SafetySeverity, Passage


# Patterns that indicate an attempt to defeat or bypass safety systems
INTERLOCK_BYPASS_PATTERNS = [
    r'\bbypass\b.*\b(interlock|door|guard|switch|light curtain|e-stop|estop|safety)\b',
    r'\bjumper\b.*\b(safety|interlock|relay|pin|circuit|sensor|switch)\b',
    r'\bdefeat\b.*\b(guard|interlock|curtain|barrier|switch)\b',
    r'\btrick\b.*\b(sensor|interlock|switch|light curtain)\b',
    r'\boverride\b.*\b(safety|interlock|e-stop|estop|limit switch)\b',
    r'\bdisable\b.*\b(interlock|safety switch|emergency stop|light curtain|guard)\b',
    r'\brun.*(with\s+(guard|door)\s+open|interlock\s+bypassed)\b',
    r'\bbridge\b.*\b(contact|terminal|safety channel|interlock)\b',
    r'\btape\s+down\b.*\b(switch|sensor|interlock)\b'
]

# Patterns that attempt live machine control (out of scope for MVP advisory copilot)
LIVE_CONTROL_PATTERNS = [
    r'\b(start|run|spin|actuate|fire|jog|turn on)\s+(the\s+)?(spindle|motor|ram|cylinder|conveyor|press)\b',
    r'\b(override|reset)\s+(the\s+)?(plc|relay|drive)\s+remotely\b',
    r'\bforce\s+(output|coil|register|bit)\b',
    r'\bcommand\s+(motion|axis|arm)\b'
]

# Hazardous procedures requiring explicit LOTO and safety verification
HAZARDOUS_CONDITIONS = {
    "electrical": [r'\b(480v|480vac|capacitor|dc bus|megger|megohmmeter|high voltage|terminal strip tb1)\b'],
    "hydraulic": [r'\b(hydraulic|320 bar|4,640 psi|accumulator|relief valve|rv-1|high pressure)\b'],
    "thermal": [r'\b(sealing jaw|heater|210 deg|160 deg|burn hazard)\b'],
    "pinch_crush": [r'\b(press die|forming press|cylinder ram|rotary knife|cross-cutting)\b']
}


class SafetyGuardrails:
    """Evaluates technician queries and diagnostic actions against plant safety rules."""

    def evaluate(self, query: str, matched_passages: Optional[List[Passage]] = None) -> SafetyAssessment:
        query_lower = query.lower()
        flags = []
        precautions = []
        is_safe = True
        blocked = False
        severity = SafetySeverity.SAFE
        warning_msg = ""

        # 1. Check for Interlock Bypass Attempts (CRITICAL VIOLATION)
        for pattern in INTERLOCK_BYPASS_PATTERNS:
            if re.search(pattern, query_lower):
                is_safe = False
                blocked = True
                severity = SafetySeverity.INTERLOCK_TRIP
                flags.append("INTERLOCK_BYPASS_ATTEMPT")
                warning_msg = (
                    "CRITICAL SAFETY VIOLATION: FixPilot AI prohibits bypassing, jumpering, or defeating "
                    "safety interlocks, door switches, or light curtains. Doing so violates OSHA regulations "
                    "(29 CFR 1910.147 / 1910.217) and poses immediate risk of lethal electrical shock, "
                    "amputation from rotating cutter/spindle, or crush injury."
                )
                precautions.append("Never jumper or bypass safety switches or safety relays.")
                precautions.append("If interlock will not clear, check mechanical alignment or replace faulty switch.")
                precautions.append("Escalate safety circuit anomalies to Plant Safety Officer immediately.")
                return SafetyAssessment(
                    is_safe=False,
                    severity=severity,
                    blocked=blocked,
                    flags=flags,
                    loto_required=True,
                    warning_message=warning_msg,
                    required_precautions=precautions
                )

        # 2. Check for Live Machinery Control Attempt (MVP Boundary)
        for pattern in LIVE_CONTROL_PATTERNS:
            if re.search(pattern, query_lower):
                is_safe = False
                blocked = True
                severity = SafetySeverity.DANGER
                flags.append("LIVE_CONTROL_BLOCKED")
                warning_msg = (
                    "SCOPE BOUNDARY: FixPilot AI MVP is strictly an evidence-guided diagnostic copilot. "
                    "Live machine actuation, remote PLC forcing, and direct motor start commands are blocked "
                    "by design. All physical actions require human technician verification at the review gate."
                )
                precautions.append("Operate machine controls exclusively via certified local HMI/operator panels.")
                precautions.append("Follow local pre-start checklists and area clearance protocols.")
                return SafetyAssessment(
                    is_safe=False,
                    severity=severity,
                    blocked=blocked,
                    flags=flags,
                    loto_required=False,
                    warning_message=warning_msg,
                    required_precautions=precautions
                )

        # 3. Check for Hazardous High-Risk Maintenance Conditions
        combined_text = query_lower
        if matched_passages:
            combined_text += " " + " ".join(p.content.lower() for p in matched_passages)

        loto_needed = False
        for category, patterns in HAZARDOUS_CONDITIONS.items():
            for pat in patterns:
                if re.search(pat, combined_text):
                    if category == "electrical":
                        flags.append("HAZARD_ELECTRICAL_480V")
                        precautions.append("Lockout/Tagout main 480VAC disconnect switch.")
                        precautions.append("Wait minimum 10 minutes for DC bus capacitors to discharge below 50VDC.")
                        precautions.append("Verify 0.0V with a calibrated digital multimeter before contact.")
                        loto_needed = True
                    elif category == "hydraulic":
                        flags.append("HAZARD_HYDRAULIC_320BAR")
                        precautions.append("Support press ram with mechanical safety block before entry.")
                        precautions.append("Open manual tank bypass valve BV-1 to vent accumulator pressure to 0 bar.")
                        precautions.append("Never check for high-pressure fluid leaks with bare hands.")
                        loto_needed = True
                    elif category == "thermal":
                        flags.append("HAZARD_THERMAL_BURN")
                        precautions.append("Wear heat-resistant safety gloves around rotary sealing jaws (>160°C).")
                        precautions.append("Allow sealing elements to cool before servicing thermocouple or heater.")
                    elif category == "pinch_crush":
                        flags.append("HAZARD_PINCH_CRUSH")
                        precautions.append("Keep hands clear of tool carousel and rotary knife swing paths.")
                        precautions.append("Ensure zero stored mechanical energy.")
                        loto_needed = True

        if flags:
            severity = SafetySeverity.WARNING
            warning_msg = "Safety Precautions Required: Ensure zero-energy verification before proceeding."

        return SafetyAssessment(
            is_safe=is_safe,
            severity=severity,
            blocked=blocked,
            flags=flags,
            loto_required=loto_needed,
            warning_message=warning_msg,
            required_precautions=precautions
        )
