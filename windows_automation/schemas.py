"""
Data structures and schemas for Windows Automation module.

Defines ApplicationRecord, DiscoveryResult, ResolutionResult, ActionRequest,
AuthorizationDecision, VerificationEvidence, AuditRecord, and ExecutionResult.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Literal, Any, Dict, List


PermissionStatus = Literal["granted", "denied", "requires_approval"]
ActionStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
VerificationStatus = Literal[
    "launch_accepted",
    "launch_verified",
    "launch_failed",
    "cancelled",
    "denied",
    "timed_out",
    "verification_inconclusive",
]
ErrorCode = Literal[
    "ERR_INVALID_REQUEST",
    "ERR_UNSUPPORTED_ACTION",
    "ERR_TARGET_NOT_ALLOWLISTED",
    "ERR_TARGET_NOT_FOUND",
    "ERR_AMBIGUOUS_TARGET",
    "ERR_TARGET_UNAVAILABLE",
    "ERR_PERMISSION_DENIED",
    "ERR_MISSING_APPROVAL",
    "ERR_LAUNCH_FAILED",
    "ERR_VERIFICATION_FAILED",
    "ERR_TIMEOUT",
    "ERR_CANCELLED",
    "ERR_DUPLICATE_REQUEST",
    "ERR_DISCOVERY_FAILED",
]


def current_iso_timestamp() -> str:
    """Return ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ApplicationRecord:
    """
    Structured record representing a discovered or registered Windows application.
    """
    app_id: str
    display_name: str
    normalized_name: str
    executable_path: str
    source: str  # "system_builtin", "start_menu_user", "start_menu_all_users", "registry", "app_path"
    status: str = "available"  # "available", "target_missing", "unsupported"
    version: Optional[str] = None
    publisher: Optional[str] = None
    icon_path: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    launch_args: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApplicationRecord":
        return cls(
            app_id=data.get("app_id", ""),
            display_name=data.get("display_name", ""),
            normalized_name=data.get("normalized_name", ""),
            executable_path=data.get("executable_path", ""),
            source=data.get("source", "unknown"),
            status=data.get("status", "available"),
            version=data.get("version"),
            publisher=data.get("publisher"),
            icon_path=data.get("icon_path"),
            aliases=data.get("aliases", []),
            launch_args=data.get("launch_args", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DiscoveryResult:
    """Summary and details of an installed-application discovery scan."""
    applications: List[ApplicationRecord] = field(default_factory=list)
    total_discovered: int = 0
    sources_scanned: List[str] = field(default_factory=list)
    discovery_errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=current_iso_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "applications": [app.to_dict() for app in self.applications],
            "total_discovered": self.total_discovered,
            "sources_scanned": self.sources_scanned,
            "discovery_errors": self.discovery_errors,
            "timestamp": self.timestamp,
        }


@dataclass
class ResolutionResult:
    """Outcome of resolving an application query or identifier against the catalogue."""
    status: Literal["resolved", "ambiguous", "not_found", "unsupported"]
    query: str
    matched_record: Optional[ApplicationRecord] = None
    candidates: List[ApplicationRecord] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "matched_record": self.matched_record.to_dict() if self.matched_record else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "reason": self.reason,
        }


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
    app_id: Optional[str] = None
    step_id: int = 1
    parameters: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    timeout_seconds: float = 10.0
    authorization: Optional[AuthorizationDecision] = None
    resolved_record: Optional[ApplicationRecord] = None

    def __post_init__(self):
        if not self.idempotency_key:
            target_key = self.app_id or self.target
            self.idempotency_key = f"{self.task_id}:{self.step_id}:{self.action_name}:{target_key}"

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.resolved_record:
            res["resolved_record"] = self.resolved_record.to_dict()
        if self.authorization:
            res["authorization"] = self.authorization.to_dict()
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionRequest":
        auth_data = data.get("authorization")
        auth = AuthorizationDecision.from_dict(auth_data) if isinstance(auth_data, dict) else auth_data
        rec_data = data.get("resolved_record")
        rec = ApplicationRecord.from_dict(rec_data) if isinstance(rec_data, dict) else None
        return cls(
            action_id=data.get("action_id", ""),
            task_id=data.get("task_id", ""),
            step_id=int(data.get("step_id", 1)),
            action_name=data.get("action_name", ""),
            target=data.get("target", ""),
            app_id=data.get("app_id"),
            parameters=data.get("parameters", {}),
            idempotency_key=data.get("idempotency_key"),
            timeout_seconds=float(data.get("timeout_seconds", 10.0)),
            authorization=auth,
            resolved_record=rec,
        )


@dataclass
class VerificationEvidence:
    """Truthful verification results and evidence."""
    verified: bool = False
    verification_status: VerificationStatus = "launch_accepted"
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
    verification_status: VerificationStatus = "launch_accepted"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: str = field(default_factory=current_iso_timestamp)
    completed_at: str = field(default_factory=current_iso_timestamp)
    duration_ms: int = 0
    verification: VerificationEvidence = field(default_factory=VerificationEvidence)
    resolved_record: Optional[ApplicationRecord] = None
    audit: Optional[AuditRecord] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.verification:
            res["verification"] = self.verification.to_dict()
        if self.resolved_record:
            res["resolved_record"] = self.resolved_record.to_dict()
        if self.audit:
            res["audit"] = self.audit.to_dict()
        return res
