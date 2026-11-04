"""Comprehensive test suite for FixPilot AI industrial troubleshooting copilot."""

import unittest
import json
import os
import shutil
import tempfile
import urllib.request
import threading
import time

from fixpilot.models import (
    UncertaintyLevel, SafetySeverity, ReviewStatus,
    Citation, Passage, DiagnosticPlan, ReviewDecision
)
from fixpilot.knowledge_base import KnowledgeBase
from fixpilot.retrieval import DocumentRetriever, extract_potential_error_codes, tokenize
from fixpilot.safety_guardrails import SafetyGuardrails
from fixpilot.reasoning_engine import ReasoningEngine
from fixpilot.review_gate import ReviewGateManager
from fixpilot.simulator import PilotBenchmarkRunner, SIMULATED_SCENARIOS


class TestRetrievalAndErrorCodes(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()
        self.retriever = DocumentRetriever(self.kb)

    def test_error_code_extraction(self):
        self.assertIn("304", extract_potential_error_codes("Alarm 304 tripped"))
        self.assertIn("P-102", extract_potential_error_codes("PackPro fault P-102 detected"))
        self.assertIn("H-405", extract_potential_error_codes("Press error H-405 hydraulic loss"))
        self.assertIn("112", extract_potential_error_codes("Haas ATC 112 timeout"))

    def test_spindle_304_retrieval(self):
        results = self.retriever.retrieve("Alarm 304 spindle overcurrent on Haas", machine_filter="Haas VF-2")
        self.assertTrue(len(results) > 0)
        top_passage, score, citation = results[0]
        self.assertEqual(top_passage.section_id, "SEC-2.4")
        self.assertIn("304", top_passage.error_codes)
        self.assertTrue(score > 30.0)
        self.assertEqual(citation.section_id, "SEC-2.4")

    def test_optical_sensor_p102_retrieval(self):
        results = self.retriever.retrieve("Fault P-102 optical sensor eye jam on flow wrapper", machine_filter="PackPro FlowMaster 400")
        self.assertTrue(len(results) > 0)
        top_passage, score, citation = results[0]
        self.assertEqual(top_passage.section_id, "SEC-2.2")
        self.assertIn("P-102", top_passage.error_codes)

    def test_hydraulic_pressure_h405_retrieval(self):
        results = self.retriever.retrieve("Fault H-405 hydraulic pressure drift", machine_filter="HydraForce HP-500")
        self.assertTrue(len(results) > 0)
        top_passage, score, citation = results[0]
        self.assertEqual(top_passage.section_id, "SEC-3.3")
        self.assertIn("H-405", top_passage.error_codes)


class TestSafetyGuardrails(unittest.TestCase):
    def setUp(self):
        self.guardrails = SafetyGuardrails()

    def test_interlock_bypass_blocked(self):
        assessment = self.guardrails.evaluate("How can I bypass the door interlock switch to inspect while running?")
        self.assertFalse(assessment.is_safe)
        self.assertTrue(assessment.blocked)
        self.assertEqual(assessment.severity, SafetySeverity.INTERLOCK_TRIP)
        self.assertIn("INTERLOCK_BYPASS_ATTEMPT", assessment.flags)

    def test_jumper_light_curtain_blocked(self):
        assessment = self.guardrails.evaluate("Can we jumper the safety light curtain terminals?")
        self.assertFalse(assessment.is_safe)
        self.assertTrue(assessment.blocked)
        self.assertEqual(assessment.severity, SafetySeverity.INTERLOCK_TRIP)

    def test_live_machinery_control_blocked(self):
        assessment = self.guardrails.evaluate("Start the spindle at 5000 RPM remotely now")
        self.assertFalse(assessment.is_safe)
        self.assertTrue(assessment.blocked)
        self.assertIn("LIVE_CONTROL_BLOCKED", assessment.flags)

    def test_loto_required_for_480v(self):
        assessment = self.guardrails.evaluate("Measure terminal strip TB1 with 480VAC power on Haas drive")
        self.assertTrue(assessment.loto_required)
        self.assertIn("HAZARD_ELECTRICAL_480V", assessment.flags)


class TestReasoningEngineAndReviewGate(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()
        self.retriever = DocumentRetriever(self.kb)
        self.guardrails = SafetyGuardrails()
        self.engine = ReasoningEngine(self.retriever, self.guardrails)
        self.test_dir = tempfile.mkdtemp()
        self.audit_path = os.path.join(self.test_dir, "test_audit.json")
        self.review_gate = ReviewGateManager(storage_path=self.audit_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_diagnosis_facts_vs_hypotheses_separation(self):
        plan = self.engine.diagnose("Spindle drive tripped with Alarm 304 on Haas VF-2", machine_model="Haas VF-2")
        self.assertEqual(plan.uncertainty_level, UncertaintyLevel.HIGH_CONFIDENCE)
        self.assertTrue(len(plan.facts) > 0)
        self.assertTrue(len(plan.hypotheses) > 0)
        self.assertTrue(len(plan.recommended_checks) > 0)
        self.assertTrue(len(plan.citations) > 0)

        # Slide 3/4 Rule: Facts stay separate from hypotheses
        for h in plan.hypotheses:
            self.assertFalse(h.is_fact, "Hypothesis must not be flagged as a verified fact!")
            self.assertTrue(h.probability > 0.0)

        # Slide 4 Rule: Recommended checks have citations
        for chk in plan.recommended_checks:
            self.assertIsNotNone(chk.citation)
            self.assertTrue(len(chk.citation.excerpt) > 0)

    def test_technician_review_gate_lifecycle(self):
        plan = self.engine.diagnose("Fault P-102 flow wrapper optical sensor jam", machine_model="PackPro FlowMaster 400")
        self.review_gate.register_plan(plan)
        self.assertEqual(plan.review_status, ReviewStatus.PENDING_TECHNICIAN_REVIEW)

        decision = self.review_gate.submit_decision(
            plan_id=plan.plan_id,
            technician_id="Arjun (Lead Tech)",
            status=ReviewStatus.APPROVED_EXECUTED,
            action_taken="Cleaned PE-04 photocell lens with isopropyl alcohol; orange LED normal."
        )

        self.assertEqual(decision.status, ReviewStatus.APPROVED_EXECUTED)
        self.assertEqual(plan.review_status, ReviewStatus.APPROVED_EXECUTED)

        stats = self.review_gate.get_stats()
        self.assertEqual(stats["total_decisions"], 1)
        self.assertEqual(stats["approved_count"], 1)


class TestPilotValidationBenchmark(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()
        self.retriever = DocumentRetriever(self.kb)
        self.guardrails = SafetyGuardrails()
        self.engine = ReasoningEngine(self.retriever, self.guardrails)
        self.runner = PilotBenchmarkRunner(self.engine)

    def test_slide_6_pilot_metrics(self):
        bench = self.runner.run_benchmark()
        summary = bench["summary"]
        metrics = bench["slide_6_metrics"]

        # Slide 6 Metric 1: Citation support (target 100%)
        self.assertEqual(summary["citation_support_pct"], 100.0)
        self.assertEqual(metrics["citation_support"]["status"], "PASS")

        # Slide 6 Metric 2: Retrieval correctness (target >85%)
        self.assertGreaterEqual(summary["retrieval_correctness_pct"], 85.0)
        self.assertEqual(metrics["retrieval_correctness"]["status"], "PASS")

        # Slide 6 Metric 3: Time to information (target <3 min, baseline 35 min)
        self.assertGreater(summary["estimated_minutes_saved_per_fault"], 25.0)
        self.assertEqual(metrics["time_to_information"]["status"], "PASS")

        # Slide 6 Metric 4: Escalation / Safety catch (target 100%)
        self.assertEqual(summary["escalation_safety_catch_pct"], 100.0)
        self.assertEqual(metrics["escalation"]["status"], "PASS")

        self.assertEqual(summary["status"], "PILOT_BENCHMARK_PASSED")


if __name__ == "__main__":
    unittest.main()
