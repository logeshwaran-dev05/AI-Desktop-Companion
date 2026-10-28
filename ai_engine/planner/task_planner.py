
import re
from difflib import SequenceMatcher

from ai_engine.schemas.command_schema import (
    CommandRequest,
    CommandEntities,
    PlanStep,
    PlannerResponse
)


class TaskPlanner:

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

        # Step 4: Identify different command phrases
        pattern = (
            r"^(?:(?:please|can you|could you|would you)\s+)?"
            r"(open|launch|start)\b\s*(.*)$"
        )

        match = re.match(pattern, user_input)

        if match:
            action = match.group(1)
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

            # Step 6: Supported applications
            supported_applications = {
                "notepad": "Notepad"
            }

            # Step 7: Exact or spelling-based matching
            if application in supported_applications:
                application_name = supported_applications[application]

            else:
                similarities = {
                    name: SequenceMatcher(
                        None,
                        application.replace(" ", ""),
                        name.replace(" ", "")
                    ).ratio()
                    for name in supported_applications
                }

                best_match = max(
                    similarities,
                    key=similarities.get
                )

                confidence = similarities[best_match]

                if confidence >= 0.85:
                    application_name = supported_applications[best_match]

                elif confidence >= 0.65:
                    return PlannerResponse(
                        intent="open_application",
                        entities=CommandEntities(
                            application=application
                        ),
                        steps=[],
                        requires_clarification=True,
                        clarification_question=(
                            f"Did you mean {supported_applications[best_match]}?"
                        ),
                        status="clarification_required",
                        message="Application name is uncertain."
                    )

                else:
                    return PlannerResponse(
                        intent="open_application",
                        entities=CommandEntities(
                            application=application
                        ),
                        steps=[],
                        requires_clarification=False,
                        clarification_question=None,
                        status="unsupported",
                        message=(
                            f"{application} is not currently supported."
                        )
                    )

            # Step 8: Generate structured plan
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
                    f"{application_name} plan generated successfully."
                )
            )

        # Step 9: Handle unsupported commands
        return PlannerResponse(
            intent="unknown",
            entities=CommandEntities(),
            steps=[],
            requires_clarification=False,
            clarification_question=None,
            status="unsupported",
            message="This command is not currently supported."
        )
