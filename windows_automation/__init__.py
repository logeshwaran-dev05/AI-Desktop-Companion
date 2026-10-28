"""
Windows Automation — Installed Application Discovery & Safe Launch.

Created by: Logeshwaran D (Windows Automation — Safe Actions & Verification, JM Vertex Technologies)
Module: windows_automation
Milestone: Milestone 2 — Installed Application Discovery & Controlled Launch
"""

from windows_automation.schemas import (
    ApplicationRecord,
    DiscoveryResult,
    ResolutionResult,
    ActionRequest,
    ExecutionResult,
    VerificationEvidence,
    AuthorizationDecision,
    AuditRecord,
)
from windows_automation.discovery import (
    ApplicationDiscoverer,
    normalize_app_name,
    generate_stable_app_id,
    parse_lnk_file,
)
from windows_automation.catalogue import ApplicationCatalogue
from windows_automation.policy import WindowsActionPolicy
from windows_automation.verifier import WindowsWindowVerifier
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.adapter import WindowsAutomationAdapter

__all__ = [
    "ApplicationRecord",
    "DiscoveryResult",
    "ResolutionResult",
    "ApplicationDiscoverer",
    "ApplicationCatalogue",
    "WindowsActionPolicy",
    "WindowsWindowVerifier",
    "WindowsAutomationExecutor",
    "WindowsAutomationAdapter",
    "ActionRequest",
    "ExecutionResult",
    "VerificationEvidence",
    "AuthorizationDecision",
    "AuditRecord",
    "normalize_app_name",
    "generate_stable_app_id",
    "parse_lnk_file",
]
