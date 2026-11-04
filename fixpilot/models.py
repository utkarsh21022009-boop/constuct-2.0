"""Data models for FixPilot AI industrial troubleshooting copilot."""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from enum import Enum
import time
import uuid


class UncertaintyLevel(str, Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"      # Direct manual match, explicit fault code
    MEDIUM_HYPOTHESIS = "MEDIUM_HYPOTHESIS"  # Inferred from symptoms, plausible root cause
    LOW_CONFIDENCE = "LOW_CONFIDENCE"        # Partial keyword match, requires manual verification
    UNSAFE_REJECTED = "UNSAFE_REJECTED"      # Blocked by safety guardrails


class SafetySeverity(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    DANGER = "DANGER"
    INTERLOCK_TRIP = "INTERLOCK_TRIP"


class ReviewStatus(str, Enum):
    PENDING_TECHNICIAN_REVIEW = "PENDING_TECHNICIAN_REVIEW"
    APPROVED_EXECUTED = "APPROVED_EXECUTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    ESCALATED_OEM = "ESCALATED_OEM"
    RESOLVED = "RESOLVED"


@dataclass
class Citation:
    manual_id: str
    manual_title: str
    section_id: str
    section_title: str
    page_number: int
    excerpt: str
    relevance_score: float
    anchor_id: str = ""

    def __post_init__(self):
        if not self.anchor_id:
            self.anchor_id = f"{self.manual_id}-{self.section_id}".replace(" ", "_")


@dataclass
class Passage:
    passage_id: str
    manual_id: str
    manual_title: str
    machine_model: str
    section_id: str
    section_title: str
    page_number: int
    content: str
    error_codes: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    safety_warnings: List[str] = field(default_factory=list)


@dataclass
class ManualSection:
    section_id: str
    title: str
    page_number: int
    content: str
    passages: List[Passage] = field(default_factory=list)
    subsections: List['ManualSection'] = field(default_factory=list)


@dataclass
class Manual:
    manual_id: str
    title: str
    machine_model: str
    manufacturer: str
    version: str
    approval_date: str
    sections: List[ManualSection] = field(default_factory=list)
    total_pages: int = 0


@dataclass
class SafetyAssessment:
    is_safe: bool
    severity: SafetySeverity
    blocked: bool
    flags: List[str] = field(default_factory=list)
    loto_required: bool = False
    warning_message: str = ""
    required_precautions: List[str] = field(default_factory=list)


@dataclass
class RecommendedCheck:
    step_number: int
    action: str
    expected_outcome: str
    risk_level: str
    citation: Optional[Citation] = None
    verification_method: str = ""


@dataclass
class DiagnosisHypothesis:
    cause: str
    probability: float  # 0.0 to 1.0
    evidence_summary: str
    citations: List[Citation] = field(default_factory=list)
    is_fact: bool = False  # Strict separation: Facts vs Hypotheses


@dataclass
class DiagnosticPlan:
    plan_id: str
    timestamp: float
    query: str
    error_code: str
    machine_model: str
    uncertainty_level: UncertaintyLevel
    confidence_score: float
    facts: List[str] = field(default_factory=list)  # Verified direct facts from manual
    hypotheses: List[DiagnosisHypothesis] = field(default_factory=list)  # Plausible causes
    recommended_checks: List[RecommendedCheck] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    safety: SafetyAssessment = field(default_factory=lambda: SafetyAssessment(True, SafetySeverity.SAFE, False))
    review_status: ReviewStatus = ReviewStatus.PENDING_TECHNICIAN_REVIEW
    technician_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewDecision:
    decision_id: str
    plan_id: str
    technician_id: str
    status: ReviewStatus
    timestamp: float
    action_taken: str
    notes: str
    escalation_reason: Optional[str] = None
    resolution_time_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FaultScenario:
    scenario_id: str
    title: str
    machine_model: str
    error_code: str
    reported_symptoms: str
    expected_root_cause: str
    expected_section_id: str
    is_unsafe_prompt: bool = False
    unsafe_intent: Optional[str] = None
