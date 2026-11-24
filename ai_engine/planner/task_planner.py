
import re
from difflib import SequenceMatcher
from typing import Optional, Literal

from ai_engine.schemas.command_schema import (
    CommandRequest,
    CommandEntities,
    PlanStep,
    PlannerResponse,
    PlanStatus,
)

from windows_automation.adapter import WindowsAutomationAdapter
from windows_automation.catalogue import ApplicationRecord


ResolutionStatus = Literal[
    "resolved",
    "clarification_required",
    "unsupported",
]


class TaskPlanner:
    """
    Converts natural-language application commands into structured plans.

    Application discovery and validation are delegated to
    WindowsAutomationAdapter.
    """

    _default_adapter: Optional[WindowsAutomationAdapter] = None

    COMMAND_PATTERN = re.compile(
        r"^(?:please\s+)?"
        r"(?:(?:can|could)\s+you\s+)?"
        r"(?:open|launch|start|run|bring\s+up)\s+(.+?)\s*[?.!]*$",
        re.IGNORECASE,
    )

    NATURAL_LANGUAGE_PATTERN = re.compile(
        r"^(?:"
        r"i\s+want\s+to\s+(?:use|open)|"
        r"i\s+need\s+to\s+(?:use|open)|"
        r"i\s+would\s+like\s+to\s+(?:use|open)"
        r")\s+(.+?)\s*[?.!]*$",
        re.IGNORECASE,
    )

    GENERAL_QUESTION_PATTERN = re.compile(
        r"^(what|why|how|when|where|who|which|explain|define)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        adapter: Optional[WindowsAutomationAdapter] = None,
    ):
        if adapter is not None:
            self.adapter = adapter
        else:
            if TaskPlanner._default_adapter is None:
                TaskPlanner._default_adapter = (
                    WindowsAutomationAdapter(auto_discover=True)
                )

            self.adapter = TaskPlanner._default_adapter

    # ---------------------------------------------------------
    # NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def normalize(value: str) -> str:
        """Normalize application names for comparison."""

        return re.sub(
            r"[^a-z0-9]",
            "",
            (value or "").casefold(),
        )

    # ---------------------------------------------------------
    # RESPONSE CREATION
    # ---------------------------------------------------------

    def _response(
        self,
        intent: str,
        status: PlanStatus,
        message: str,
        application: Optional[str] = None,
        steps: Optional[list[PlanStep]] = None,
        clarification_question: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> PlannerResponse:
        """Create a consistent planner response."""

        return PlannerResponse(
            intent=intent,
            entities=CommandEntities(
                application=application,
                parameters=parameters or {},
            ),
            steps=steps or [],
            requires_clarification=(
                status == "clarification_required"
            ),
            clarification_question=clarification_question,
            status=status,
            message=message,
        )

    # ---------------------------------------------------------
    # COMMAND EXTRACTION
    # ---------------------------------------------------------

    def _extract_target(self, text: str) -> Optional[str]:
        """Extract the requested application from a command."""

        cleaned = " ".join((text or "").strip().split())

        match = self.COMMAND_PATTERN.match(cleaned)

        if match:
            return match.group(1).strip(" .?!")

        match = self.NATURAL_LANGUAGE_PATTERN.match(cleaned)

        if match:
            return match.group(1).strip(" .?!")

        # Handle a command containing only an action.
        if re.match(
            r"^(?:please\s+)?(?:open|launch|start|run)\s*[?.!]*$",
            cleaned,
            re.IGNORECASE,
        ):
            return ""

        return None

    # ---------------------------------------------------------
    # FUZZY APPLICATION MATCHING
    # ---------------------------------------------------------

    def _find_fuzzy_match(
        self,
        query: str,
    ) -> tuple[
        Optional[ApplicationRecord],
        float,
        list[ApplicationRecord],
    ]:
        """
        Find likely spelling corrections using dynamically
        discovered application records.

        Reject candidates whose name lengths differ too much,
        preventing unrelated applications from being suggested.
        """

        normalized_query = self.normalize(query)

        if not normalized_query:
            return None, 0.0, []

        records = self.adapter.get_catalogue().get_all()

        scored: list[tuple[float, ApplicationRecord]] = []

        for record in records:
            candidates = [
                record.display_name,
                record.app_id,
                *(record.aliases or []),
            ]

            best_score = 0.0

            for candidate_name in candidates:
                if not isinstance(candidate_name, str):
                    continue

                normalized_candidate = self.normalize(
                    candidate_name
                )

                if not normalized_candidate:
                    continue

                length_difference = abs(
                    len(normalized_query)
                    - len(normalized_candidate)
                )

                allowed_difference = max(
                    2,
                    round(len(normalized_query) * 0.20),
                )

                if length_difference > allowed_difference:
                    continue

                score = SequenceMatcher(
                    None,
                    normalized_query,
                    normalized_candidate,
                ).ratio()

                best_score = max(best_score, score)

            if best_score > 0:
                scored.append((best_score, record))

        if not scored:
            return None, 0.0, []

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        best_score = scored[0][0]

        possible_matches = [
            record
            for score, record in scored
            if score >= 0.78
        ]

        # Avoid automatically choosing between similarly scored apps.
        if (
            len(scored) > 1
            and best_score - scored[1][0] < 0.06
        ):
            return None, best_score, possible_matches

        return scored[0][1], best_score, possible_matches

    # ---------------------------------------------------------
    # APPLICATION RESOLUTION
    # ---------------------------------------------------------

    def _resolve_application(
        self,
        query: str,
    ) -> tuple[
        ResolutionStatus,
        Optional[ApplicationRecord],
        Optional[str],
    ]:
        """
        Resolve an application through Windows Automation.

        Exact matches are accepted.
        Partial names require clarification.
        Typographical corrections are validated dynamically.
        """

        resolution = self.adapter.resolve_application(query)

        if resolution.status == "resolved":
            record = resolution.matched_record

            if record is None:
                return "unsupported", None, None

            normalized_query = self.normalize(query)
            normalized_name = self.normalize(
                record.display_name
            )

            normalized_aliases = {
                self.normalize(alias)
                for alias in (record.aliases or [])
                if alias
            }

            is_exact = (
                normalized_query == normalized_name
                or normalized_query == self.normalize(record.app_id)
                or normalized_query in normalized_aliases
            )

            if is_exact:
                return "resolved", record, None

            is_prefix = (
                normalized_name.startswith(normalized_query)
                or any(
                    alias.startswith(normalized_query)
                    for alias in normalized_aliases
                )
            )

            if is_prefix:
                return (
                    "clarification_required",
                    record,
                    f"Did you mean {record.display_name}?",
                )

            return "unsupported", None, None

        if resolution.status == "ambiguous":
            names = [
                record.display_name
                for record in resolution.candidates[:5]
            ]

            return (
                "clarification_required",
                None,
                "Which application did you mean? "
                + ", ".join(names),
            )

        # Try spelling correction when there is no direct match.
        candidate, confidence, possible_matches = (
            self._find_fuzzy_match(query)
        )

        if candidate is not None and confidence >= 0.86:
            verified = self.adapter.resolve_application(
                candidate.display_name
            )

            if (
                verified.status == "resolved"
                and verified.matched_record is not None
            ):
                return (
                    "resolved",
                    verified.matched_record,
                    None,
                )

        # Ask for confirmation only when a sufficiently close
        # candidate has been found.
        if confidence >= 0.78 and possible_matches:
            names = [
                record.display_name
                for record in possible_matches[:3]
            ]

            return (
                "clarification_required",
                None,
                "Did you mean one of these applications? "
                + ", ".join(names),
            )

        return "unsupported", None, None

    # ---------------------------------------------------------
    # MAIN COMMAND PROCESSING
    # ---------------------------------------------------------

    def process_command(
        self,
        request: CommandRequest,
    ) -> PlannerResponse:
        """Understand a command and generate a structured plan."""

        text = " ".join(
            (request.text or "").strip().split()
        )

        # 1. Empty input.
        if not text:
            return self._response(
                intent="unknown",
                status="clarification_required",
                message="No command was provided.",
                clarification_question=(
                    "What would you like me to do?"
                ),
            )

        # 2. General questions.
        if self.GENERAL_QUESTION_PATTERN.match(text):
            return self._response(
                intent="general_question",
                status="plan_ready",
                message="This is a general question.",
            )

        # 3. Extract the requested application.
        target = self._extract_target(text)

        if target is None:
            return self._response(
                intent="unknown",
                status="unsupported",
                message=(
                    "I could not identify a supported command."
                ),
            )

        # 4. Missing application.
        if not target:
            return self._response(
                intent="open_application",
                status="clarification_required",
                message="The application name is missing.",
                clarification_question=(
                    "Which application would you like to open?"
                ),
            )

        # 5. Resolve application dynamically.
        status, record, question = (
            self._resolve_application(target)
        )

        if status == "clarification_required":
            return self._response(
                intent="open_application",
                status="clarification_required",
                message=(
                    "The application name needs clarification."
                ),
                clarification_question=question,
            )

        if status == "unsupported" or record is None:
            return self._response(
                intent="open_application",
                status="unsupported",
                message=(
                    "No supported installed application "
                    f"was found matching '{target}'."
                ),
            )

        # 6. Create the application launch plan.
        # Stable application IDs are used for execution.
        step = PlanStep(
            step_id=1,
            action="open_application",
            target=record.app_id,
            depends_on=[],
            expected_outcome=(
                f"{record.display_name} is opened successfully."
            ),
            parameters={
                "application_name": record.display_name,
            },
        )

        return self._response(
            intent="open_application",
            status="plan_ready",
            message=(
                "Application launch plan created successfully."
            ),
            application=record.display_name,
            steps=[step],
        )
