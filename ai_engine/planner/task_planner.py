
from ai_engine.schemas.command_schema import (
    CommandRequest,
    CommandEntities,
    PlanStep,
    PlannerResponse
)


class TaskPlanner:

    def process_command(self, request: CommandRequest) -> PlannerResponse:

        # Step 1: Get and clean user input
        user_input = request.text.strip()

        # Step 2: Handle empty input
        if not user_input:
            return PlannerResponse(
                intent="unknown",
                entities=CommandEntities(),
                steps=[],
                requires_clarification=True,
                clarification_question="Please enter a command.",
                status="clarification_required"
            )

        command = user_input.lower()

        # Step 3: Identify general questions
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
                status="plan_ready"
            )

        # Step 4: Identify application opening commands
        action_words = ("open ", "launch ", "start ", "open")

        if command.startswith(action_words):

            # Extract application name safely
            parts = user_input.split(maxsplit=1)

            application = (
                parts[1].strip()
                if len(parts) > 1
                else ""
            )

            # Step 5: Handle missing application
            if not application:
                return PlannerResponse(
                    intent="open_application",
                    entities=CommandEntities(),
                    steps=[],
                    requires_clarification=True,
                    clarification_question=(
                        "Which application would you like to open?"
                    ),
                    status="clarification_required"
                )

            # Step 6: Check supported applications
            supported_applications = ["notepad"]

            if application.lower() not in supported_applications:
                return PlannerResponse(
                    intent="open_application",
                    entities=CommandEntities(
                        application=application
                    ),
                    steps=[],
                    requires_clarification=False,
                    clarification_question=None,
                    status="unsupported"
                )

            # Step 7: Generate structured plan
            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(
                    application="Notepad"
                ),
                steps=[
                    PlanStep(
                        step_id=1,
                        action="open_application",
                        target="Notepad",
                        depends_on=[],
                        expected_outcome=(
                            "Notepad should open successfully."
                        )
                    )
                ],
                requires_clarification=False,
                clarification_question=None,
                status="plan_ready"
            )

        # Step 8: Handle unknown commands
        return PlannerResponse(
            intent="unknown",
            entities=CommandEntities(),
            steps=[],
            requires_clarification=True,
            clarification_question=(
                "I could not understand your instruction. "
                "Could you please explain what you want to do?"
            ),
            status="clarification_required"
        )
