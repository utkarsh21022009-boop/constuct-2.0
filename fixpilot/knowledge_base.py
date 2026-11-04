"""Knowledge base loader and repository for approved equipment manuals."""

import json
import os
import re
from typing import List, Dict, Optional, Tuple
from fixpilot.models import Manual, ManualSection, Passage


# Standard approved industrial manuals included with FixPilot MVP
DEFAULT_MANUALS: List[Dict] = [
    {
        "manual_id": "MAN-HAAS-VF2-2024",
        "title": "Haas VF-Series VMC Maintenance & Troubleshooting Manual",
        "machine_model": "Haas VF-2",
        "manufacturer": "Haas Automation Inc.",
        "version": "Rev 14.2",
        "approval_date": "2024-01-15",
        "total_pages": 142,
        "sections": [
            {
                "section_id": "SEC-1.1",
                "title": "General Machine Safety & Lockout/Tagout (LOTO)",
                "page_number": 4,
                "content": "All maintenance personnel must strictly follow OSHA Lockout/Tagout (LOTO) 29 CFR 1910.147. Before accessing the electrical cabinet or mechanical enclosures, shut off the main disconnect switch, apply personal padlock, and verify zero electrical and pneumatic energy. NEVER defeat, jumper, or bridge electrical door interlock switches or safety limit switches. Bypassing interlocks exposes technicians to lethal rotating spindle hazards (up to 12,000 RPM) and axis crush hazards.",
                "passages": [
                    {
                        "passage_id": "HAAS-1.1-P1",
                        "content": "Before opening the main electrical enclosure or replacing drive amplifiers, disconnect main three-phase 480VAC power and wait a minimum of 10 minutes for DC bus high-voltage capacitors to bleed down below 50VDC. Always measure DC bus terminals with a calibrated multimeter before touching bus bars.",
                        "error_codes": ["LOTO", "SAFETY"],
                        "keywords": ["lockout", "tagout", "loto", "capacitor", "bus", "voltage", "hazard", "cabinet"],
                        "safety_warnings": ["Lethal 480VAC electrical shock hazard", "10-minute capacitor bleed-down required"]
                    },
                    {
                        "passage_id": "HAAS-1.1-P2",
                        "content": "Safety Door Interlocks: Enclosure door switch (S1) is monitored by the dual-channel safety relay. Bypassing, defeating, or altering door interlock sensors is strictly forbidden by plant policy and machine firmware. Firmware fault ALM-990 triggers permanently if tamper or jumpering is detected across safety channel contacts.",
                        "error_codes": ["ALM-990", "INTERLOCK"],
                        "keywords": ["door interlock", "bypass", "jumper", "tamper", "safety relay", "defeat"],
                        "safety_warnings": ["Do NOT bypass door interlocks under any circumstances"]
                    }
                ]
            },
            {
                "section_id": "SEC-2.4",
                "title": "Spindle Drive Subsystem & Overcurrent Faults (Alarm 304)",
                "page_number": 38,
                "content": "Alarm 304: SPINDLE DRIVE OVERCURRENT / OVERLOAD TRIP. This alarm indicates that the digital vector drive spindle amplifier (VFD) has detected current exceeding 150% of nominal drive rating for longer than 3.5 seconds, or instantaneous IGBT overcurrent (>220A peak). Common root causes include: 1) Physical mechanical spindle seizure or bearing race spalling; 2) Drive cable phase-to-ground or phase-to-phase insulation breakdown; 3) Motor winding short-circuit due to coolant ingress into the spindle stator junction box; 4) Faulty Hall effect current transducer on the vector drive PCB.",
                "passages": [
                    {
                        "passage_id": "HAAS-2.4-P1",
                        "content": "Alarm 304 - Diagnostic Step 1 (Physical Inspection): With the main power OFF and spindle stopped, rotate the spindle cartridge by hand. The spindle must rotate smoothly without rough detents or abnormal drag. If the spindle cannot be turned by hand, inspect for tool holder taper galling, seized ceramic front bearings, or spindle lock pin failure.",
                        "error_codes": ["304", "ALM-304", "ALARM 304"],
                        "keywords": ["spindle", "overcurrent", "alarm 304", "drag", "bearing", "seizure", "hand rotation"],
                        "safety_warnings": ["Ensure spindle drive is in E-Stop before manually rotating tool taper"]
                    },
                    {
                        "passage_id": "HAAS-2.4-P2",
                        "content": "Alarm 304 - Diagnostic Step 2 (Motor Winding Insulation Test): Disconnect motor power leads U, V, W at the vector drive terminal strip TB1. Using a 500V Megohmmeter (Megger), test insulation resistance from each phase (U-GND, V-GND, W-GND). Resistance must be greater than 10 Megohms. If insulation is under 1 Megohm, inspect the spindle motor terminal housing for coolant contamination or degraded stator coils.",
                        "error_codes": ["304", "ALM-304", "ALARM 304"],
                        "keywords": ["spindle", "megohmmeter", "insulation", "winding", "coolant", "megger", "resistance"],
                        "safety_warnings": ["Verify 0V on DC bus before removing motor leads U, V, W"]
                    },
                    {
                        "passage_id": "HAAS-2.4-P3",
                        "content": "Alarm 304 - Diagnostic Step 3 (Regenerative Braking Resistor Check): Measure resistance across regenerative resistor terminals R1 and R2 on the vector drive. Nominal resistance is 6.0 Ohms (+/- 5%). If open-circuit (OL) or shorted, the drive will fault with Alarm 304 during rapid spindle deceleration cycles.",
                        "error_codes": ["304", "ALM-304", "REGEN"],
                        "keywords": ["regen", "braking", "resistor", "spindle", "deceleration", "resistance"],
                        "safety_warnings": ["Resistor bank can exceed 80 deg C during normal operation; allow to cool"]
                    }
                ]
            },
            {
                "section_id": "SEC-4.2",
                "title": "Automatic Tool Changer (ATC) Diagnostic (Alarm 112)",
                "page_number": 62,
                "content": "Alarm 112: TOOL CHANGER ARM TIMEOUT. Occurs when the double-arm tool changer fails to complete 60-degree or 180-degree rotation within the allocated 1.8 second cycle window. Frequently caused by low pneumatic cylinder pressure (<85 PSI), dry arm spline splines requiring lithium grease, or misadjusted proximity switches Prox 1 (Arm at Carousel) and Prox 2 (Arm at Spindle).",
                "passages": [
                    {
                        "passage_id": "HAAS-4.2-P1",
                        "content": "Alarm 112 Verification: Inspect the main shop air regulator gauge at the rear service panel. Minimum operational air pressure for ATC double-arm stroke is 85 PSI (5.8 bar). If pressure dips during tool change cycle, purge pneumatic water separator bowl and clean the inline air regulator filter cartridge.",
                        "error_codes": ["112", "ALM-112", "ATC"],
                        "keywords": ["atc", "tool changer", "timeout", "alarm 112", "pneumatic", "air pressure", "psi"],
                        "safety_warnings": ["Keep hands clear of carousel swing radius during manual recovery mode"]
                    },
                    {
                        "passage_id": "HAAS-4.2-P2",
                        "content": "Alarm 112 Proximity Sensor Alignment: Access Diagnostic Parameter Screen Page 2. Verify LED status of inputs 'ARM AT POCKET' and 'ARM AT SPINDLE'. Clearance between inductive proximity target and sensor face must be 1.0mm to 1.5mm. Clean metal swarf and chips off sensor tip using a non-metallic scraper.",
                        "error_codes": ["112", "ALM-112"],
                        "keywords": ["proximity sensor", "arm", "chips", "swarf", "alignment", "gap"],
                        "safety_warnings": ["Lock out machine feed before entering carousel enclosure"]
                    }
                ]
            },
            {
                "section_id": "SEC-5.1",
                "title": "Axis Servo Drive & Encoder Faults (Alarm 102 / 104)",
                "page_number": 88,
                "content": "Alarm 102 (X-Axis Servomotor Overheat) and Alarm 104 (Z-Axis Servomotor Overheat). Caused by excessive axis friction, worn ball screw thrust bearings, or blocked cooling ducting on the brushless AC servomotor frame.",
                "passages": [
                    {
                        "passage_id": "HAAS-5.1-P1",
                        "content": "Alarm 102/104 Diagnostic: Check lube system pressure gauge during axis jog. Ensure way lube reservoir is filled with Mobil Vactra #2 and lube cycle delivers 35 PSI pulses every 15 minutes. Check ball screw temperature with infrared thermometer. Normal operating temperature is below 45 deg C.",
                        "error_codes": ["102", "104", "ALM-102", "ALM-104"],
                        "keywords": ["servo", "overheat", "alarm 102", "alarm 104", "way lube", "ball screw", "temperature"],
                        "safety_warnings": ["Ensure axis is blocked against gravity drop before servicing Z-axis brake"]
                    }
                ]
            }
        ]
    },
    {
        "manual_id": "MAN-PACKPRO-400-2023",
        "title": "PackPro 400 Horizontal Flow Wrapper Service & Maintenance Manual",
        "machine_model": "PackPro FlowMaster 400",
        "manufacturer": "Packaging Automation Technologies Corp.",
        "version": "Release 3.1",
        "approval_date": "2023-08-20",
        "total_pages": 96,
        "sections": [
            {
                "section_id": "SEC-1.0",
                "title": "Machine Guarding & Emergency Stop Circuit",
                "page_number": 3,
                "content": "The PackPro 400 is equipped with interlocked tunnel guards over the infeed conveyor, fin seal rollers, and rotary end seal jaws. Opening any guard instantly drops out the master control relay (MCR) via dual safety contactors. Never defeat guard limit switches with magnetic bypass clips or wiring jumpers. Doing so creates an extreme amputation hazard around the rotary cross-cutting knife.",
                "passages": [
                    {
                        "passage_id": "PACK-1.0-P1",
                        "content": "Safety Guard Circuit: If guard open alarm MCR-01 will not clear, check safety interlock switch keyed actuators for physical bending or loose mounting screws. Never insert foreign objects or bypass switches to run machine with guards open.",
                        "error_codes": ["MCR-01", "INTERLOCK"],
                        "keywords": ["guard", "interlock", "mcr", "emergency stop", "knife", "amputation"],
                        "safety_warnings": ["High amputation hazard from rotary knife - do not bypass guards"]
                    }
                ]
            },
            {
                "section_id": "SEC-2.2",
                "title": "Photoelectric Registration Eye & Infeed Jams (Fault P-102)",
                "page_number": 27,
                "content": "Fault P-102: OPTICAL REGISTRATION SENSOR / INFEED JAM. This fault triggers when the print registration optical sensor fails to detect three consecutive eye marks on the packaging film, or when the infeed photocell detects continuous product blockage exceeding 850mm.",
                "passages": [
                    {
                        "passage_id": "PACK-2.2-P1",
                        "content": "Fault P-102 - Optical Eye Sensor Diagnostic: Check photoelectric eye lens (Sick / Banner sensor PE-04) mounted above film feed roll. Dust, product crumbs, or electrostatic powder buildup on the optical lens attenuates the light beam. Clean lens using isopropyl alcohol (IPA) and lint-free microfiber cloth. Inspect sensor signal LED; orange LED should toggle sharply as dark print eye-mark passes the focal spot (target distance: 12.5mm +/- 1mm).",
                        "error_codes": ["P-102", "P102", "FAULT P-102"],
                        "keywords": ["p-102", "optical sensor", "registration eye", "lens", "photocell", "dust", "crumbs", "led", "clean"],
                        "safety_warnings": ["Ensure machine is in PAUSE or STOP before cleaning sensor lens"]
                    },
                    {
                        "passage_id": "PACK-2.2-P2",
                        "content": "Fault P-102 - Film Tension & Dancer Arm Alignment: If lens is clean but P-102 persists, check film web tension. A slack or jumping film causes the eye mark to drift outside the detection gate window (+/- 5mm). Verify pneumatic dancer arm back-pressure is set to 2.2 bar on regulator PR-3. Check dancer potentiometer cable for loose terminal connections (pins 3 & 4 on junction box JB-2).",
                        "error_codes": ["P-102", "P102", "FAULT P-102"],
                        "keywords": ["p-102", "film tension", "dancer arm", "loose connection", "registration", "potentiometer"],
                        "safety_warnings": ["Do not adjust tension while film is moving at full production speed"]
                    },
                    {
                        "passage_id": "PACK-2.2-P3",
                        "content": "Fault P-102 - Infeed Conveyor Jam Clear: If optical eye is operating correctly, fault is caused by physical product pileup at the forming shoe entrance. Stop machine, open infeed side access hatch, and clear jammed product packages. Inspect infeed lug chain pitch and verify timing mark alignment with master servo index.",
                        "error_codes": ["P-102", "P102", "JAM"],
                        "keywords": ["p-102", "jam", "forming shoe", "product pileup", "infeed", "lug chain"],
                        "safety_warnings": ["Clear jams using plastic clearing paddle, never hands inside knife zone"]
                    }
                ]
            },
            {
                "section_id": "SEC-3.1",
                "title": "Rotary Sealing Jaws & Heater Temperature Alarm (Fault P-205)",
                "page_number": 45,
                "content": "Fault P-205: SEALING JAW HEATER TEMPERATURE UNDER-RANGE. Indicates upper or lower rotary crimper temperature has fallen 15 deg C below recipe setpoint for more than 45 seconds.",
                "passages": [
                    {
                        "passage_id": "PACK-3.1-P1",
                        "content": "Fault P-205 Diagnostic: 1) Verify thermocouple J-type probe resistance (nominal 10-15 Ohms at ambient). 2) Check rotary slip ring carbon brush assembly for wear or carbon buildup. Worn slip ring brushes cause intermittent heater contact and thermocouple noise.",
                        "error_codes": ["P-205", "P205", "FAULT P-205"],
                        "keywords": ["p-205", "heater", "sealing jaw", "thermocouple", "slip ring", "temperature"],
                        "safety_warnings": ["Sealing jaws operate at 160-210 deg C. Severe burn hazard! Wear heat-resistant gloves."]
                    }
                ]
            }
        ]
    },
    {
        "manual_id": "MAN-HYDRA-500T-2022",
        "title": "HydraForce 500-Ton Hydraulic Forming Press Operation & Troubleshooting",
        "machine_model": "HydraForce HP-500",
        "manufacturer": "HydraForce Heavy Industrial Equipment Ltd.",
        "version": "Rev 5.0",
        "approval_date": "2022-11-10",
        "total_pages": 180,
        "sections": [
            {
                "section_id": "SEC-1.2",
                "title": "High-Pressure Hydraulic Safety & Light Curtain Interlock",
                "page_number": 6,
                "content": "DANGER: System operating pressure reaches 320 bar (4,640 PSI). Pin-hole hydraulic oil leaks under this pressure will penetrate human skin causing devastating injection injuries requiring immediate surgical amputation. NEVER test for leaks with fingers, hands, or bare skin; use cardboard or wood. The Category 4 safety light curtain (OSHA 1910.217) mutes only during the non-hazardous upstroke. Defeating light curtains by blanking without key switch authorization or bridging safety outputs is a catastrophic safety violation.",
                "passages": [
                    {
                        "passage_id": "HYDRA-1.2-P1",
                        "content": "Zero Energy State Protocol: Before any hydraulic maintenance or filter replacement: 1) Support main ram slide with mechanical safety block; 2) Shut down main 75kW pump motor; 3) Open manual tank bypass ball valve BV-1 to vent accumulator pressure; 4) Verify main pressure gauge read 0 bar before loosening any fitting.",
                        "error_codes": ["LOTO", "SAFETY-HYD"],
                        "keywords": ["hydraulic safety", "zero energy", "accumulator", "injection hazard", "ram block"],
                        "safety_warnings": ["Catastrophic high-pressure injection injury hazard (320 bar)", "Always insert mechanical ram safety block before entering press die area"]
                    },
                    {
                        "passage_id": "HYDRA-1.2-P2",
                        "content": "Light Curtain Safety Interlock: Optical safety beams monitor the front press daylight opening. If any beam is interrupted during downward pressing stroke, proportional valves de-energize and hydraulic safety dump valves drop pilot pressure within 45ms. Never attempt to jumper safety contactor K1 or bypass safety inputs.",
                        "error_codes": ["INTERLOCK", "CURTAIN"],
                        "keywords": ["light curtain", "interlock", "bypass", "dump valve", "safety beam"],
                        "safety_warnings": ["Defeating light curtain interlock is strictly prohibited"]
                    }
                ]
            },
            {
                "section_id": "SEC-3.3",
                "title": "Hydraulic Power Unit (HPU) Pressure Drift & Low Pressure (Fault H-405)",
                "page_number": 74,
                "content": "Fault H-405: HYDRAULIC PRESSURE INTERLOCK LOST / DRIFT. Main system manifold pressure failed to attain target holding pressure (minimum 220 bar) within 2.5 seconds of clamp command, or pressure decayed below 180 bar during tonnage hold cycle.",
                "passages": [
                    {
                        "passage_id": "HYDRA-3.3-P1",
                        "content": "Fault H-405 - Diagnostic Step 1 (Main Proportional Relief Valve RV-1): Inspect proportional relief valve RV-1 on the primary manifold. Contaminants in hydraulic fluid (ISO VG 46) frequently jam the pilot poppet in an unseated position, dumping pump flow directly back to tank. Check RV-1 solenoid coil resistance: nominal 19.5 Ohms (+/- 1.5 Ohms). If open or shorted, replace coil.",
                        "error_codes": ["H-405", "H405", "FAULT H-405"],
                        "keywords": ["h-405", "hydraulic pressure", "relief valve", "rv-1", "drift", "pilot poppet", "manifold", "poppet"],
                        "safety_warnings": ["Depressurize accumulator (open BV-1) and verify 0 bar before removing valve cartridge"]
                    },
                    {
                        "passage_id": "HYDRA-3.3-P2",
                        "content": "Fault H-405 - Diagnostic Step 2 (Hydraulic Suction Strainer & Fluid Level): Check sight glass on main 600-liter oil tank. If oil level is below mid-sight glass, pump cavitation occurs. Inspect return filter differential pressure indicator (gauge DPG-2). If red flag popped, replace 10-micron element immediately. Aerated or foaming oil in sight glass indicates loose pump suction hose clamp.",
                        "error_codes": ["H-405", "H405", "FAULT H-405"],
                        "keywords": ["h-405", "oil level", "filter", "cavitation", "suction strainer", "differential pressure"],
                        "safety_warnings": ["Allow oil to cool below 40 deg C before changing filter element"]
                    },
                    {
                        "passage_id": "HYDRA-3.3-P3",
                        "content": "Fault H-405 - Diagnostic Step 3 (Main Cylinder Piston Seal Bypass Test): If pump delivers 250 bar dead-head against test block but press cannot hold tonnage, internal piston seal bypass is present. Perform slip-ring drain test: disconnect cylinder B-port return line to tank, hold pressure at 200 bar, and measure leakage. Permissible leakage is under 50 ml/minute. Leakage exceeding 200 ml/minute requires repacking cylinder chevron seals.",
                        "error_codes": ["H-405", "H405"],
                        "keywords": ["h-405", "cylinder seal", "bypass", "leakage", "tonnage hold", "chevron seal"],
                        "safety_warnings": ["Catch hydraulic oil in containment basin; wipe up spills immediately to prevent slip hazard"]
                    }
                ]
            }
        ]
    }
]


class KnowledgeBase:
    """Manages approved equipment manuals and passage indexes."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except OSError:
            self.data_dir = "/tmp"
        self.manuals: Dict[str, Manual] = {}
        self.all_passages: List[Passage] = []
        self._init_knowledge_base()

    def _init_knowledge_base(self):
        """Load default manuals and any saved custom manuals."""
        for man_data in DEFAULT_MANUALS:
            self._load_manual_from_dict(man_data)

        # Check for any custom JSON manuals saved in data directory
        for fname in os.listdir(self.data_dir):
            if fname.endswith(".json") and not fname.startswith(".") and fname != "audit_log.json":
                filepath = os.path.join(self.data_dir, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "manual_id" in data:
                            self._load_manual_from_dict(data)
                except Exception as e:
                    print(f"Error loading custom manual {fname}: {e}")

    def _load_manual_from_dict(self, data: Dict) -> Manual:
        sections: List[ManualSection] = []
        for sec_data in data.get("sections", []):
            passages: List[Passage] = []
            for pass_data in sec_data.get("passages", []):
                p = Passage(
                    passage_id=pass_data["passage_id"],
                    manual_id=data["manual_id"],
                    manual_title=data["title"],
                    machine_model=data.get("machine_model", "Standard"),
                    section_id=sec_data["section_id"],
                    section_title=sec_data["title"],
                    page_number=sec_data.get("page_number", 1),
                    content=pass_data["content"],
                    error_codes=pass_data.get("error_codes", []),
                    keywords=pass_data.get("keywords", []),
                    safety_warnings=pass_data.get("safety_warnings", [])
                )
                passages.append(p)
                self.all_passages.append(p)

            s = ManualSection(
                section_id=sec_data["section_id"],
                title=sec_data["title"],
                page_number=sec_data.get("page_number", 1),
                content=sec_data.get("content", ""),
                passages=passages
            )
            sections.append(s)

        manual = Manual(
            manual_id=data["manual_id"],
            title=data["title"],
            machine_model=data.get("machine_model", "Standard"),
            manufacturer=data.get("manufacturer", "OEM"),
            version=data.get("version", "1.0"),
            approval_date=data.get("approval_date", "2024-01-01"),
            sections=sections,
            total_pages=data.get("total_pages", len(sections) * 10)
        )
        self.manuals[manual.manual_id] = manual
        return manual

    def get_manual(self, manual_id: str) -> Optional[Manual]:
        return self.manuals.get(manual_id)

    def list_manuals(self) -> List[Dict]:
        return [
            {
                "manual_id": m.manual_id,
                "title": m.title,
                "machine_model": m.machine_model,
                "manufacturer": m.manufacturer,
                "version": m.version,
                "approval_date": m.approval_date,
                "total_pages": m.total_pages,
                "section_count": len(m.sections),
                "sections": [{"section_id": s.section_id, "title": s.title, "page": s.page_number} for s in m.sections]
            }
            for m in self.manuals.values()
        ]

    def add_custom_manual(self, manual_dict: Dict) -> Manual:
        """Add and persist a new approved equipment manual."""
        manual = self._load_manual_from_dict(manual_dict)
        save_path = os.path.join(self.data_dir, f"{manual.manual_id}.json")
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(manual_dict, f, indent=2)
        return manual
