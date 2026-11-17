"""
Capability Registry – maps an application identifier to its automation adapter class
and declares the list of supported actions.

Usage:
    from api.capability_registry import registry
    registry.register('chrome', ChromeAdapter, ['open', 'navigate', 'search'])
    adapter_cls = registry.get_adapter('chrome')
    caps = registry.list_capabilities('chrome')
"""

from typing import Dict, List, Type

# The concrete adapters live in api.adapters.* and all inherit from
# windows_automation.adapter.WindowsAutomationAdapter (or the local BaseAdapter).

class CapabilityRegistry:
    def __init__(self):
        self._adapters: Dict[str, Type] = {}
        self._capabilities: Dict[str, List[str]] = {}

    def register(self, app_id: str, adapter_cls: Type, capabilities: List[str]) -> None:
        """Register an adapter and its supported action names.

        *app_id* – canonical identifier used throughout the catalogue.
        *adapter_cls* – a class (not an instance) that implements the required
        adapter contract (execute_plan_step, cancel_action, etc.).
        *capabilities* – list of strings such as ['open', 'navigate', 'search'].
        """
        key = app_id.lower()
        self._adapters[key] = adapter_cls
        self._capabilities[key] = [c.lower() for c in capabilities]

    def get_adapter(self, app_id: str):
        """Return the adapter class for *app_id* or ``None`` if not registered."""
        return self._adapters.get(app_id.lower())

    def list_capabilities(self, app_id: str) -> List[str]:
        """Return the list of supported actions for *app_id* (empty list if unknown)."""
        return self._capabilities.get(app_id.lower(), []).copy()

    def is_supported(self, app_id: str, action: str) -> bool:
        """Check whether *action* is declared for *app_id*."""
        return action.lower() in self.list_capabilities(app_id)

# Global singleton used by the whole backend
registry = CapabilityRegistry()
