"""
Data structures and schemas for Windows Automation module.

Defines ActionRequest, AuthorizationDecision, VerificationEvidence,
AuditRecord, and ExecutionResult.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Literal, Any, Dict, List


PermissionStatus = Literal["granted", "denied", "requires_approval"]
ActionStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
ErrorCode = Literal[
    "ERR_INVALID_REQUEST",
    "ERR_UNSUPPORTED_ACTION",
    "ERR_TARGET_NOT_ALLOWLISTED",
    "ERR_PERMISSION_DENIED",
    "ERR_MISSING_APPROVAL",
    "ERR_LAUNCH_FAILED",
    "ERR_VERIFICATION_FAILED",
    "ERR_TIMEOUT",
    "ERR_CANCELLED",
    "ERR_DUPLICATE_REQUEST",
]


def current_iso_timestamp() -> str:
    """Return ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuthorizationDecision:
    """Security and authorization decision associated with an action."""
    decision_id: str
    permission_status: PermissionStatus = "denied"
    requires_user_approval: bool = False
    approval_reference: Optional[str] = None
    evaluated_at: str = field(default_factory=current_iso_timestamp)
    reason: str = ""

    def is_authorized(self) -> bool:
        if self.permission_status != "granted":
            return False
        if self.requires_user_approval and not self.approval_reference:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthorizationDecision":
        return cls(
            decision_id=data.get("decision_id", ""),
            permission_status=data.get("permission_status", "denied"),
            requires_user_approval=bool(data.get("requires_user_approval", False)),
            approval_reference=data.get("approval_reference"),
            evaluated_at=data.get("evaluated_at", current_iso_timestamp()),
            reason=data.get("reason", ""),
        )


@dataclass
class ActionRequest:
    """Discrete action request received for automation execution."""
    action_id: str
    task_id: str
    action_name: str
    target: str
    step_id: int = 1
    parameters: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    timeout_seconds: float = 10.0
    authorization: Optional[AuthorizationDecision] = None

    def __post_init__(self):
        if not self.idempotency_key:
            self.idempotency_key = f"{self.task_id}:{self.step_id}:{self.action_name}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionRequest":
        auth_data = data.get("authorization")
        auth = AuthorizationDecision.from_dict(auth_data) if isinstance(auth_data, dict) else auth_data
        return cls(
            action_id=data.get("action_id", ""),
            task_id=data.get("task_id", ""),
            step_id=int(data.get("step_id", 1)),
            action_name=data.get("action_name", ""),
            target=data.get("target", ""),
            parameters=data.get("parameters", {}),
            idempotency_key=data.get("idempotency_key"),
            timeout_seconds=float(data.get("timeout_seconds", 10.0)),
            authorization=auth,
        )


@dataclass
class VerificationEvidence:
    """Truthful verification results and evidence."""
    verified: bool = False
    method: str = "none"
    details: Dict[str, Any] = field(default_factory=dict)
    evidence_timestamp: str = field(default_factory=current_iso_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditRecord:
    """Redacted audit log event for an automation step."""
    event_type: str
    action_id: str
    task_id: str
    timestamp: str = field(default_factory=current_iso_timestamp)
    redacted_summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    """Structured execution outcome returned by the Windows Automation executor."""
    action_id: str
    task_id: str
    status: ActionStatus
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: str = field(default_factory=current_iso_timestamp)
    completed_at: str = field(default_factory=current_iso_timestamp)
    duration_ms: int = 0
    verification: VerificationEvidence = field(default_factory=VerificationEvidence)
    audit: Optional[AuditRecord] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
