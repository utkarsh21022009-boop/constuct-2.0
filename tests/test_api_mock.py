"""API dispatching tests without network socket dependencies."""

import unittest
import json
import io
from fixpilot.server import FixPilotApp, FixPilotRequestHandler
from fixpilot.models import ReviewStatus


class MockSocket:
    def __init__(self, request_bytes):
        self.rfile = io.BytesIO(request_bytes)
        self.wfile = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if 'r' in mode:
            return self.rfile
        return self.wfile


class TestFixPilotAPI(unittest.TestCase):
    def setUp(self):
        self.app = FixPilotApp()

    def test_status_api(self):
        status_data = {
            "status": "ONLINE",
            "app": "FixPilot AI",
            "manuals_count": len(self.app.kb.manuals),
            "passages_indexed": len(self.app.kb.all_passages),
            "scenarios_available": 5,
            "review_gate_active": True
        }
        self.assertEqual(status_data["status"], "ONLINE")
        self.assertEqual(status_data["app"], "FixPilot AI")
        self.assertGreaterEqual(status_data["passages_indexed"], 5)

    def test_diagnose_api_logic(self):
        plan = self.app.engine.diagnose("Alarm 304 spindle overcurrent on Haas VF-2", machine_model="Haas VF-2")
        self.app.review_gate.register_plan(plan)
        plan_dict = plan.to_dict()

        self.assertIn("plan_id", plan_dict)
        self.assertIn("facts", plan_dict)
        self.assertIn("hypotheses", plan_dict)
        self.assertIn("recommended_checks", plan_dict)
        self.assertIn("citations", plan_dict)
        self.assertTrue(len(plan_dict["recommended_checks"]) >= 2)

    def test_review_gate_submission(self):
        plan = self.app.engine.diagnose("Fault P-102 flow wrapper optical sensor", machine_model="PackPro FlowMaster 400")
        self.app.review_gate.register_plan(plan)

        decision = self.app.review_gate.submit_decision(
            plan_id=plan.plan_id,
            technician_id="Arjun (Lead Tech)",
            status=ReviewStatus.APPROVED_EXECUTED,
            action_taken="Cleaned lens on PE-04; machine resumed production."
        )

        self.assertEqual(decision.plan_id, plan.plan_id)
        self.assertEqual(decision.status, ReviewStatus.APPROVED_EXECUTED)

        stats = self.app.review_gate.get_stats()
        self.assertGreaterEqual(stats["approved_count"], 1)

    def test_benchmark_api_logic(self):
        bench = self.app.benchmark_runner.run_benchmark()
        self.assertEqual(bench["summary"]["status"], "PILOT_BENCHMARK_PASSED")
        self.assertEqual(bench["summary"]["citation_support_pct"], 100.0)
        self.assertEqual(bench["summary"]["retrieval_correctness_pct"], 100.0)
        self.assertEqual(bench["summary"]["escalation_safety_catch_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
