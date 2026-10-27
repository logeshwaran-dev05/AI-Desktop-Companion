
from ai_engine.schemas.command_schema import (
    CommandRequest,
    CommandEntities,
    PlanStep,
    PlannerResponse
)


class TaskPlanner:

    def process_command(self, request: CommandRequest) -> PlannerResponse:

        # Step 1: Clean user input
        user_input = request.text.strip()

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

        command = user_input.lower()

        # Step 3: Handle general questions
        question_words = (
            "what ", "why ", "how ",
            "when ", "where ", "who "
        )

        if command.startswith(question_words):
            return PlannerResponse(
                intent="general_question",
                entities=CommandEntities(),
                steps=[],
                requires_clarification=False,
                clarification_question=None,
                status="plan_ready",
                message="General question identified."
            )

        # Step 4: Identify application-opening commands
        parts = command.split(maxsplit=1)
        action = parts[0]

        if action in ("open", "launch", "start"):

            # Step 5: Check application name
            if len(parts) == 1 or not parts[1].strip():
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

            application = parts[1].strip()

            # Step 6: Check supported applications
            supported_applications = {
                "notepad": "Notepad"
            }

            if application not in supported_applications:
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

            # Step 7: Generate structured plan
            application_name = supported_applications[application]

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

        # Step 8: Handle unsupported commands
        return PlannerResponse(
            intent="unknown",
            entities=CommandEntities(),
            steps=[],
            requires_clarification=False,
            clarification_question=None,
            status="unsupported",
            message=(
                "This command is not currently supported."
            )
        )
