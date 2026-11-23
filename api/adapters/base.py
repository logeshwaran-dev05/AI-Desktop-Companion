import abc
from typing import Any, Dict, Set

class UnsupportedAction(Exception):
    pass

class BaseAdapter(abc.ABC):
    """Abstract base class for all application adapters.

    Each adapter implements a set of *capabilities* (actions) that can be executed
    on the target application.  The adapter receives the catalogue entry for the
    application on construction, which contains the launch target, method, etc.
    """

    app_id: str
    name: str
    category: str
    capabilities: Set[str]

    def __init__(self, catalogue_entry: Dict[str, Any]):
        self.entry = catalogue_entry
        self.app_id = catalogue_entry.get("app_id")
        self.name = catalogue_entry.get("app_name")
        self.capabilities = set()
        self._prepare()

    @abc.abstractmethod
    def _prepare(self) -> None:
        """Perform any heavy‑weight initialisation (e.g. start a driver)."""

    @abc.abstractmethod
    def execute(self, action: str, **kwargs) -> Any:
        """Execute *action* with the supplied ``kwargs``.

        Must raise :class:`UnsupportedAction` if the action is not part of
        ``self.capabilities``.
        """

    @abc.abstractmethod
    def verify(self, action: str, **kwargs) -> bool:
        """Return ``True`` when the expected outcome of *action* can be verified.
        May be a no‑op for actions that have no reliable verification.
        """

