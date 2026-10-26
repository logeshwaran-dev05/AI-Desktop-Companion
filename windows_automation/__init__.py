"""
Windows Automation — Safe Actions & Verification Module.

Created by: Logeshwaran D (Windows Automation — Safe Actions & Verification, JM Vertex Technologies)
Module: windows_automation
Milestone: Milestone 1 — Validated & Verified "Open Notepad" Launch
"""

from windows_automation.schemas import (
    ActionRequest,
    ExecutionResult,
    VerificationEvidence,
    AuthorizationDecision,
    AuditRecord,
)
from windows_automation.policy import WindowsActionPolicy
from windows_automation.verifier import WindowsWindowVerifier
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.adapter import WindowsAutomationAdapter

__all__ = [
    "ActionRequest",
    "ExecutionResult",
    "VerificationEvidence",
    "AuthorizationDecision",
    "AuditRecord",
    "WindowsActionPolicy",
    "WindowsWindowVerifier",
    "WindowsAutomationExecutor",
    "WindowsAutomationAdapter",
]
