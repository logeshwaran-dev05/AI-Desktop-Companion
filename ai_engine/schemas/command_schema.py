
from dataclasses import dataclass, field
from typing import Optional, Literal

# Supported input types
InputType = Literal["text", "voice"]

# Supported languages
Language = Literal["en", "ta", "tanglish"]

# Planner statuses
PlanStatus = Literal[
    "plan_ready",
    "clarification_required",
    "unsupported"
]


@dataclass
class CommandRequest:
    """Stores the original user command."""
    text: str
    input_type: InputType = "text"
    language: Language = "en"


@dataclass
class CommandEntities:
    """Stores important information extracted from a command."""
    application: Optional[str] = None
    url: Optional[str] = None
    file_path: Optional[str] = None
    parameters: dict = field(default_factory=dict)


@dataclass
class PlanStep:
    """Represents one step in a task plan."""
    step_id: int
    action: str
    target: str
    depends_on: list[int] = field(default_factory=list)
    expected_outcome: str = ""


@dataclass
class PlannerResponse:
    """Stores the structured result from the command handler."""
    intent: str
    entities: CommandEntities
    steps: list[PlanStep]
    requires_clarification: bool
    clarification_question: Optional[str]
    status: PlanStatus
    message: str = ""
