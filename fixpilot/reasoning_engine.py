"""Reasoning Engine for FixPilot AI.
Transforms approved documentation passages into a structured troubleshooting plan:
- Strict separation of Facts vs. Hypotheses
- Step-by-step Recommended Checks with exact citations
- Uncertainty labeling and confidence scoring
- Prepares the review gate for technician sign-off
"""

import time
import uuid
from typing import List, Dict, Optional, Tuple
from fixpilot.models import (
    DiagnosticPlan, DiagnosisHypothesis, RecommendedCheck, Citation,
    UncertaintyLevel, ReviewStatus, SafetyAssessment, SafetySeverity, Passage
)
from fixpilot.retrieval import DocumentRetriever, extract_potential_error_codes
from fixpilot.safety_guardrails import SafetyGuardrails


class ReasoningEngine:
    """Evidence-grounded diagnostic plan synthesizer."""

    def __init__(self, retriever: DocumentRetriever, guardrails: SafetyGuardrails):
        self.retriever = retriever
        self.guardrails = guardrails

    def diagnose(self, query: str, machine_model: Optional[str] = None) -> DiagnosticPlan:
        plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
        timestamp = time.time()
        error_codes = extract_potential_error_codes(query)
        primary_code = error_codes[0] if error_codes else "GENERAL_FAULT"

        # Step 1: Retrieve top evidence passages
        retrieval_results = self.retriever.retrieve(query, machine_filter=machine_model, top_k=4)
        matched_passages = [p for p, score, cit in retrieval_results]
        citations = [cit for p, score, cit in retrieval_results]

        # Step 2: Evaluate Safety Guardrails
        safety = self.guardrails.evaluate(query, matched_passages)

        # If blocked by safety guardrails (e.g. interlock bypass attempt)
        if safety.blocked:
            return DiagnosticPlan(
                plan_id=plan_id,
                timestamp=timestamp,
                query=query,
                error_code=primary_code,
                machine_model=machine_model or "Industrial Machine",
                uncertainty_level=UncertaintyLevel.UNSAFE_REJECTED,
                confidence_score=0.0,
                facts=[
                    "SAFETY TRIP: The requested action violates certified equipment safety interlocks or plant safety rules.",
                    f"Violation Category: {', '.join(safety.flags)}",
                    "OSHA 29 CFR 1910.147 / 1910.217 strictly forbids defeating safety devices."
                ],
                hypotheses=[],
                recommended_checks=[
                    RecommendedCheck(
                        step_number=1,
                        action="HALT TROUBLESHOOTING. Do NOT bypass interlock or bridge safety contacts.",
                        expected_outcome="All machinery remains in safe zero-motion state.",
                        risk_level="CRITICAL",
                        verification_method="Visual inspection of safety barrier"
                    ),
                    RecommendedCheck(
                        step_number=2,
                        action="Inspect the physical condition of the safety switch, key actuator, and wiring for mechanical damage or misalignment.",
                        expected_outcome="Switch opens/closes cleanly without sticking or broken actuator tongues.",
                        risk_level="MEDIUM",
                        verification_method="Multimeter continuity test with power OFF"
                    ),
                    RecommendedCheck(
                        step_number=3,
                        action="Escalate to Plant Safety Officer or OEM Certified Technician.",
                        expected_outcome="Safety interlock certified before resuming machine operation.",
                        risk_level="LOW",
                        verification_method="Formal escalation sign-off"
                    )
                ],
                citations=citations[:1] if citations else [],
                safety=safety,
                review_status=ReviewStatus.PENDING_TECHNICIAN_REVIEW,
                technician_notes="Auto-flagged for safety escalation."
            )

        # If no relevant passages found in approved manuals
        if not retrieval_results:
            return DiagnosticPlan(
                plan_id=plan_id,
                timestamp=timestamp,
                query=query,
                error_code=primary_code,
                machine_model=machine_model or "Unknown",
                uncertainty_level=UncertaintyLevel.LOW_CONFIDENCE,
                confidence_score=0.15,
                facts=["No matching troubleshooting procedures found in approved OEM equipment documentation."],
                hypotheses=[
                    DiagnosisHypothesis(
                        cause="Unrecorded fault or proprietary OEM sub-assembly fault",
                        probability=0.3,
                        evidence_summary="No approved documentation matches the query terms. FixPilot refuses to guess ungrounded root causes.",
                        citations=[],
                        is_fact=False
                    )
                ],
                recommended_checks=[
                    RecommendedCheck(
                        step_number=1,
                        action="Verify exact machine model, serial number, and firmware version on nameplate.",
                        expected_outcome="Accurate equipment metadata acquired.",
                        risk_level="LOW",
                        verification_method="Nameplate check"
                    ),
                    RecommendedCheck(
                        step_number=2,
                        action="Escalate issue to OEM Field Service or Senior Plant Engineer with diagnostic log dump.",
                        expected_outcome="OEM service ticket opened.",
                        risk_level="LOW",
                        verification_method="Escalation ticket"
                    )
                ],
                citations=[],
                safety=safety,
                review_status=ReviewStatus.PENDING_TECHNICIAN_REVIEW,
                technician_notes="Low confidence: no manual passages matched."
            )

        # Step 3: Extract Verified Facts directly from approved citations
        facts: List[str] = []
        top_passage, top_score, top_citation = retrieval_results[0]
        detected_machine = top_passage.manual_title.split(" ")[0]

        facts.append(
            f"OEM Reference [{top_passage.section_id} - {top_passage.section_title}]: "
            f"Approved document '{top_passage.manual_title}' page {top_passage.page_number}."
        )

        # Extract specific fact sentences from matched passages
        for p, score, cit in retrieval_results[:2]:
            sentences = [s.strip() for s in p.content.split(". ") if len(s.strip()) > 20]
            if sentences:
                facts.append(f"Fact from Section {p.section_id}: {sentences[0]}.")

        # Step 4: Synthesize Grounded Hypotheses (Separation of Facts vs Hypotheses)
        hypotheses: List[DiagnosisHypothesis] = []

        # Analyze content across retrieved passages to identify distinct root causes
        for i, (p, score, cit) in enumerate(retrieval_results[:3]):
            # Infer plausible root cause from passage context
            cause_title = "Primary Mechanical/Electrical Deviation"
            if "sensor" in p.content.lower() or "optical" in p.content.lower():
                cause_title = "Optical Sensor Obstruction or Lens Contamination"
            elif "bearing" in p.content.lower() or "seizure" in p.content.lower():
                cause_title = "Mechanical Binding / Spindle Bearing Resistance"
            elif "winding" in p.content.lower() or "insulation" in p.content.lower() or "megger" in p.content.lower():
                cause_title = "Motor Stator Insulation Breakdown / Coolant Contamination"
            elif "resistor" in p.content.lower() or "regen" in p.content.lower():
                cause_title = "Regenerative Braking Resistor Fault / Open Circuit"
            elif "relief valve" in p.content.lower() or "rv-1" in p.content.lower():
                cause_title = "Hydraulic Relief Valve Pilot Poppet Contamination"
            elif "air pressure" in p.content.lower() or "pneumatic" in p.content.lower() or "psi" in p.content.lower():
                cause_title = "Pneumatic Supply Pressure Drop / Regulator Clog"
            elif "dancer" in p.content.lower() or "tension" in p.content.lower():
                cause_title = "Film Web Tension Drift / Loose Potentiometer Wire"
            elif "seal" in p.content.lower() or "bypass" in p.content.lower():
                cause_title = "Hydraulic Cylinder Chevron Seal Internal Bypass"
            else:
                cause_title = f"Component Fault per {p.section_title}"

            # Calculate probability based on retrieval rank and match score
            prob = max(0.2, min(0.92, round(0.85 - (i * 0.18), 2)))
            summary = (
                f"Supported by manual section {p.section_id}. "
                f"Evidence: {p.content[:160]}..."
            )

            hypotheses.append(
                DiagnosisHypothesis(
                    cause=cause_title,
                    probability=prob,
                    evidence_summary=summary,
                    citations=[cit],
                    is_fact=False  # Explicitly flagged as hypothesis
                )
            )

        # Step 5: Synthesize Step-by-Step Recommended Checks
        recommended_checks: List[RecommendedCheck] = []
        for step_idx, (p, score, cit) in enumerate(retrieval_results[:3], start=1):
            # Parse procedural text
            content_lower = p.content.lower()
            risk = "LOW"
            if "480v" in content_lower or "megger" in content_lower or "320 bar" in content_lower:
                risk = "HIGH"
            elif "pneumatic" in content_lower or "disassemble" in content_lower or "heater" in content_lower:
                risk = "MEDIUM"

            # Create focused actionable check
            action_text = f"Perform procedural check per Section {p.section_id}: {p.content[:190]}."
            outcome_text = f"Conforms to manufacturer threshold in {cit.manual_title}."
            method = "Physical / Instrument Inspection"
            if "multimeter" in content_lower or "resistance" in content_lower or "megger" in content_lower:
                method = "Calibrated Multimeter / Megohmmeter"
            elif "gauge" in content_lower or "bar" in content_lower or "psi" in content_lower:
                method = "Pressure Gauge / Calibrated Transducer"
            elif "clean" in content_lower or "wipe" in content_lower:
                method = "Lint-free wipe & IPA solvent inspection"

            recommended_checks.append(
                RecommendedCheck(
                    step_number=step_idx,
                    action=action_text,
                    expected_outcome=outcome_text,
                    risk_level=risk,
                    citation=cit,
                    verification_method=method
                )
            )

        # Step 6: Determine Uncertainty Level
        if top_score > 30.0:
            uncertainty = UncertaintyLevel.HIGH_CONFIDENCE
            confidence_score = min(0.96, round(0.80 + (top_score / 200.0), 2))
        elif top_score > 10.0:
            uncertainty = UncertaintyLevel.MEDIUM_HYPOTHESIS
            confidence_score = min(0.78, round(0.55 + (top_score / 100.0), 2))
        else:
            uncertainty = UncertaintyLevel.LOW_CONFIDENCE
            confidence_score = 0.42

        return DiagnosticPlan(
            plan_id=plan_id,
            timestamp=timestamp,
            query=query,
            error_code=primary_code,
            machine_model=machine_model or detected_machine,
            uncertainty_level=uncertainty,
            confidence_score=confidence_score,
            facts=facts,
            hypotheses=hypotheses,
            recommended_checks=recommended_checks,
            citations=citations,
            safety=safety,
            review_status=ReviewStatus.PENDING_TECHNICIAN_REVIEW,
            technician_notes="Awaiting technician review gate decision."
        )
