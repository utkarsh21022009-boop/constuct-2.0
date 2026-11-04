"""Technician Review Gate and Maintenance Audit Logger.
Enforces the core design principle:
'The assistant proposes, a qualified technician decides.'
"""

import time
import uuid
import json
import os
from typing import List, Dict, Optional, Any
from fixpilot.models import (
    DiagnosticPlan, ReviewDecision, ReviewStatus
)


class ReviewGateManager:
    """Manages technician review decisions and maintenance logs."""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            # Fall back to /tmp if default directory is read-only (e.g. Vercel serverless)
            default_dir = os.path.join(os.path.dirname(__file__), "data")
            try:
                os.makedirs(default_dir, exist_ok=True)
                test_file = os.path.join(default_dir, ".test_write")
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
                self.storage_path = os.path.join(default_dir, "audit_log.json")
            except OSError:
                self.storage_path = "/tmp/audit_log.json"
        else:
            self.storage_path = storage_path

        self.plans: Dict[str, DiagnosticPlan] = {}
        self.decisions: List[ReviewDecision] = []
        self._load_decisions()

    def _load_decisions(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        d = ReviewDecision(
                            decision_id=item["decision_id"],
                            plan_id=item["plan_id"],
                            technician_id=item.get("technician_id", "TECH-01"),
                            status=ReviewStatus(item["status"]),
                            timestamp=item["timestamp"],
                            action_taken=item["action_taken"],
                            notes=item.get("notes", ""),
                            escalation_reason=item.get("escalation_reason"),
                            resolution_time_seconds=item.get("resolution_time_seconds", 0.0)
                        )
                        self.decisions.append(d)
            except Exception as e:
                print(f"Failed to load audit log: {e}")

    def _save_decisions(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([d.to_dict() for d in self.decisions], f, indent=2)
        except Exception as e:
            print(f"Failed to save audit log: {e}")

    def register_plan(self, plan: DiagnosticPlan):
        self.plans[plan.plan_id] = plan

    def get_plan(self, plan_id: str) -> Optional[DiagnosticPlan]:
        return self.plans.get(plan_id)

    def submit_decision(
        self,
        plan_id: str,
        technician_id: str,
        status: ReviewStatus,
        action_taken: str,
        notes: str = "",
        escalation_reason: Optional[str] = None
    ) -> ReviewDecision:
        """Record the qualified technician's decision at the review gate."""
        plan = self.plans.get(plan_id)
        duration = 0.0
        if plan:
            plan.review_status = status
            plan.technician_notes = notes
            duration = max(0.0, time.time() - plan.timestamp)

        decision = ReviewDecision(
            decision_id=f"DEC-{uuid.uuid4().hex[:8].upper()}",
            plan_id=plan_id,
            technician_id=technician_id or "Arjun (Lead Tech)",
            status=status,
            timestamp=time.time(),
            action_taken=action_taken,
            notes=notes,
            escalation_reason=escalation_reason,
            resolution_time_seconds=round(duration, 1)
        )
        self.decisions.insert(0, decision)
        self._save_decisions()
        return decision

    def get_audit_trail(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.decisions[:limit]]

    def get_stats(self) -> Dict[str, Any]:
        total = len(self.decisions)
        approved = sum(1 for d in self.decisions if d.status == ReviewStatus.APPROVED_EXECUTED)
        escalated = sum(1 for d in self.decisions if d.status == ReviewStatus.ESCALATED_OEM)
        resolved = sum(1 for d in self.decisions if d.status == ReviewStatus.RESOLVED)
        inconclusive = sum(1 for d in self.decisions if d.status == ReviewStatus.INCONCLUSIVE)

        avg_time = 0.0
        times = [d.resolution_time_seconds for d in self.decisions if d.resolution_time_seconds > 0]
        if times:
            avg_time = round(sum(times) / len(times), 1)

        return {
            "total_decisions": total,
            "approved_count": approved,
            "escalated_count": escalated,
            "resolved_count": resolved,
            "inconclusive_count": inconclusive,
            "avg_time_to_decision_sec": avg_time
        }
