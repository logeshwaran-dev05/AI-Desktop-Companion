
import re
from difflib import SequenceMatcher

from ai_engine.schemas.command_schema import (
    CommandRequest,
    CommandEntities,
    PlanStep,
    PlannerResponse
)

from ai_engine.catalogue import get_installed_apps


class TaskPlanner:

    @staticmethod
    def normalize(value):
        """Normalize names for application matching."""
        return re.sub(r"\s+", "", value.lower().strip())

    def process_command(self, request: CommandRequest) -> PlannerResponse:

        # Step 1: Normalize input
        user_input = " ".join(request.text.split()).lower()

        # Step 2: Handle empty input
        if not user_input:
            return PlannerResponse(
                intent="unknown",
                entities=CommandEntities(),
                steps=[],
                requires_clarification=True,
                clarification_question="Please enter a command.",
                status="clarification_required",
                message="Command cannot be empty."
            )

        # Step 3: Handle general questions
        question_words = (
            "what ", "why ", "how ",
            "when ", "where ", "who "
        )

        if user_input.startswith(question_words):
            return PlannerResponse(
                intent="general_question",
                entities=CommandEntities(),
                steps=[],
                requires_clarification=False,
                clarification_question=None,
                status="plan_ready",
                message="General question identified."
            )

        # Step 4: Identify application launch commands
        pattern = (
            r"^(?:(?:please|can you|could you|would you)\s+)?"
            r"(open|launch|start)\b\s*(.*)$"
        )

        match = re.match(pattern, user_input)

        if not match:
            return PlannerResponse(
                intent="unknown",
                entities=CommandEntities(),
                steps=[],
                requires_clarification=False,
                clarification_question=None,
                status="unsupported",
                message="This command is not currently supported."
            )

        application = match.group(2).strip()

        # Step 5: Handle missing application name
        if not application:
            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(),
                steps=[],
                requires_clarification=True,
                clarification_question=(
                    "Which application would you like to open?"
                ),
                status="clarification_required",
                message="Application name is missing."
            )

        # Step 6: Get installed application catalogue
        installed_apps = get_installed_apps()

        if not installed_apps:
            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(application=application),
                steps=[],
                requires_clarification=False,
                clarification_question=None,
                status="unsupported",
                message="No installed applications are available."
            )

        # Step 7: Match application names, IDs and aliases
        requested_name = self.normalize(application)
        matches = []

        for app in installed_apps:
            candidates = [
                app["app_name"],
                app["app_id"],
                *app.get("aliases", [])
            ]

            scores = [
                SequenceMatcher(
                    None,
                    requested_name,
                    self.normalize(candidate)
                ).ratio()
                for candidate in candidates
            ]

            confidence = max(scores)

            # Exact name, ID or alias match
            if any(
                requested_name == self.normalize(candidate)
                for candidate in candidates
            ):
                confidence = 1.0

            matches.append({
                "app": app,
                "confidence": confidence
            })

        # Step 8: Sort by confidence
        matches.sort(
            key=lambda item: item["confidence"],
            reverse=True
        )

        best_match = matches[0]
        best_confidence = best_match["confidence"]

        possible_matches = [
            item for item in matches
            if item["confidence"] >= 0.65
        ]

        # Step 9: Detect genuinely close matches
        if (
            len(possible_matches) > 1
            and possible_matches[1]["confidence"]
            >= best_confidence - 0.10
        ):
            app_names = [
                item["app"]["app_name"]
                for item in possible_matches
                if item["confidence"] >= best_confidence - 0.10
            ]

            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(
                    application=application
                ),
                steps=[],
                requires_clarification=True,
                clarification_question=(
                    "Which application did you mean: "
                    + " or ".join(app_names) + "?"
                ),
                status="clarification_required",
                message="Multiple application matches found."
            )

        # Step 10: Accept high-confidence match
        if best_confidence >= 0.85:
            selected_app = best_match["app"]
            application_name = selected_app["app_name"]

            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(
                    application=application_name
                ),
                steps=[
                    PlanStep(
                        step_id=1,
                        action="open_application",
                        target=application_name,
                        depends_on=[],
                        expected_outcome=(
                            f"{application_name} should open successfully."
                        )
                    )
                ],
                requires_clarification=False,
                clarification_question=None,
                status="plan_ready",
                message=(
                    f"{application_name} matched successfully."
                )
            )

        # Step 11: Ask clarification for medium confidence
        if best_confidence >= 0.65:
            suggested_app = best_match["app"]["app_name"]

            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(application=application),
                steps=[],
                requires_clarification=True,
                clarification_question=(
                    f"Did you mean {suggested_app}?"
                ),
                status="clarification_required",
                message="Application name is uncertain."
            )

        # Step 12: Reject low-confidence match
        return PlannerResponse(
            intent="open_application",
            entities=CommandEntities(application=application),
            steps=[],
            requires_clarification=False,
            clarification_question=None,
            status="unsupported",
            message=f"{application} is not currently available."
        )
