
from dataclasses import dataclass, field
from typing import Optional, Literal


# Supported input types
InputType = Literal["text", "voice"]

# Supported languages
Language = Literal["en", "ta", "tanglish"]

# Possible planner statuses
PlanStatus = Literal[
    "plan_ready",
    "clarification_required",
    "unsupported"
]


# 1. User command request
@dataclass
class CommandRequest:
    text: str
    input_type: InputType = "text"
    language: Language = "en"


# 2. Extracted entities
@dataclass
class CommandEntities:
    application: Optional[str] = None
    url: Optional[str] = None
    file_path: Optional[str] = None
    parameters: dict = field(default_factory=dict)


# 3. Individual task step
@dataclass
class PlanStep:
    step_id: int
    action: str
    target: str
    depends_on: list[int] = field(default_factory=list)
    expected_outcome: str = ""


# 4. Structured planner response
@dataclass
class PlannerResponse:
    intent: str
    entities: CommandEntities
    steps: list[PlanStep]
    requires_clarification: bool
    clarification_question: Optional[str]
    status: PlanStatus
