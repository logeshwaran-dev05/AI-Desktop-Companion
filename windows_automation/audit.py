"""
Structured audit logger and sensitive information redactor for Windows Automation.

Ensures safety audit trails are recorded without capturing screenshots,
monitoring clipboards, or exposing credentials / auth tokens.
"""

import re
from typing import Any, Dict, List
from windows_automation.schemas import AuditRecord, current_iso_timestamp

# Sensitive keys to redact
SENSITIVE_KEY_PATTERNS = re.compile(
    r"(password|token|secret|api[_-]?key|auth|bearer|credential|cert|private)",
    re.IGNORECASE,
)


def redact_sensitive_value(value: Any) -> Any:
    """Recursively redact sensitive fields from dictionaries or values."""
    if isinstance(value, dict):
        redacted = {}
        for k, v in value.items():
            if SENSITIVE_KEY_PATTERNS.search(str(k)):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_value(v)
        return redacted
    elif isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    elif isinstance(value, str):
        # Redact patterns resembling tokens or bearer credentials
        redacted = re.sub(
            r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]{8,}|token[:=]\s*[a-zA-Z0-9_\-\.]{8,})",
            r"[REDACTED_CREDENTIAL]",
            value,
        )
        return redacted
    return value


class AuditLogger:
    """Maintains an in-memory audit log of automation actions."""

    def __init__(self):
        self._records: List[AuditRecord] = []

    def log_event(
        self,
        event_type: str,
        action_id: str,
        task_id: str,
        summary: str,
        details: Dict[str, Any] = None,
    ) -> AuditRecord:
        """Create and store a redacted audit record."""
        details = details or {}
        safe_details = redact_sensitive_value(details)
        safe_summary = redact_sensitive_value(summary)

        record = AuditRecord(
            event_type=event_type,
            action_id=action_id,
            task_id=task_id,
            timestamp=current_iso_timestamp(),
            redacted_summary=str(safe_summary),
            details=safe_details if isinstance(safe_details, dict) else {"raw": safe_details},
        )
        self._records.append(record)
        return record

    def get_records(self, task_id: str = None) -> List[AuditRecord]:
        """Return all records or records filtered by task_id."""
        if task_id:
            return [r for r in self._records if r.task_id == task_id]
        return list(self._records)

    def clear(self):
        """Clear recorded events."""
        self._records.clear()
