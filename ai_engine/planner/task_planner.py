
import re
from difflib import SequenceMatcher

from ai_engine.schemas.command_schema import (
    CommandRequest,
    CommandEntities,
    PlanStep,
    PlannerResponse
)

from ai_engine.catalogue import get_installed_apps
from ai_engine.nlp.entity_extractor import EntityExtractor


class TaskPlanner:

    def __init__(self):
        self.entity_extractor = EntityExtractor()

    @staticmethod
    def normalize(value):
        """Normalize names for application matching."""
        return re.sub(r"\s+", "", value.lower().strip())

    def _match_application(self, application, installed_apps):
        """Find the best matching installed application."""

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

            if any(
                requested_name == self.normalize(candidate)
                for candidate in candidates
            ):
                confidence = 1.0

            matches.append({
                "app": app,
                "confidence": confidence
            })

        matches.sort(
            key=lambda item: item["confidence"],
            reverse=True
        )

        return matches

    def _build_media_plan(self, user_input, entities):
        """
        Build an ordered plan for YouTube and ChatGPT commands.

        These steps describe intended actions. The execution layer
        must support the corresponding action names.
        """

        application = entities.get("application")
        search_query = entities.get("search_query")
        prompt = entities.get("prompt")
        video_index = entities.get("video_index")
        profile_name = entities.get("profile_name")
        profile_directory = entities.get("profile_directory")

        steps = []
        parameters = {}

        if profile_name:
            parameters["profile_name"] = profile_name

        if profile_directory:
            parameters["profile_directory"] = profile_directory

        # Step 1: Open the requested website.

        if application == "youtube":
            steps.append(
                PlanStep(
                    step_id=1,
                    action="open_website",
                    target="YouTube",
                    depends_on=[],
                    expected_outcome="YouTube should open successfully."
                )
            )

        elif application == "chatgpt":
            steps.append(
                PlanStep(
                    step_id=1,
                    action="open_website",
                    target="ChatGPT",
                    depends_on=[],
                    expected_outcome="ChatGPT should open successfully."
                )
            )

        # Step 2: Search on YouTube.

        if application == "youtube" and search_query:

            parameters["search_query"] = search_query

            steps.append(
                PlanStep(
                    step_id=len(steps) + 1,
                    action="search",
                    target=search_query,
                    depends_on=[steps[-1].step_id],
                    expected_outcome=(
                        f"Search results for '{search_query}' "
                        "should be displayed."
                    )
                )
            )

        # Step 3: Play the requested video.

        play_requested = bool(
            re.search(
                r"\b(play|select|click|watch)\b",
                user_input,
                re.IGNORECASE
            )
        )

        if application == "youtube" and play_requested:

            if video_index is None:
                return None, None, (
                    "Which video would you like to play?"
                )

            parameters["video_index"] = video_index

            steps.append(
                PlanStep(
                    step_id=len(steps) + 1,
                    action="play_video",
                    target=str(video_index),
                    depends_on=[steps[-1].step_id],
                    expected_outcome=(
                        f"Video number {video_index + 1} "
                        "should start playing."
                    )
                )
            )

        # Step 4: Ask ChatGPT a prompt.

        if application == "chatgpt" and prompt:

            parameters["prompt"] = prompt

            steps.append(
                PlanStep(
                    step_id=len(steps) + 1,
                    action="ask_prompt",
                    target=prompt,
                    depends_on=[steps[-1].step_id],
                    expected_outcome=(
                        "ChatGPT should receive and respond "
                        "to the requested prompt."
                    )
                )
            )

        if len(steps) <= 1:
            return None, None, None

        return steps, parameters, None

    def process_command(self, request: CommandRequest) -> PlannerResponse:

        # Step 1: Normalize input.

        original_input = " ".join(request.text.split())
        user_input = original_input.lower()

        # Step 2: Handle empty input.

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

        # Step 3: Handle general questions.

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

        # Step 4: Extract entities.

        extracted = self.entity_extractor.extract_entities(
            original_input
        )

        application = extracted.get("application")

        # Step 5: Handle YouTube and ChatGPT multi-step commands.

        if application in ("youtube", "chatgpt"):

            media_result = self._build_media_plan(
                user_input,
                extracted
            )

            steps, parameters, clarification = media_result

            if clarification:
                return PlannerResponse(
                    intent="multi_step",
                    entities=CommandEntities(
                        application=application,
                        parameters=extracted
                    ),
                    steps=[],
                    requires_clarification=True,
                    clarification_question=clarification,
                    status="clarification_required",
                    message="More information is required."
                )

            if steps:
                return PlannerResponse(
                    intent="multi_step",
                    entities=CommandEntities(
                        application=application,
                        parameters=parameters
                    ),
                    steps=steps,
                    requires_clarification=False,
                    clarification_question=None,
                    status="plan_ready",
                    message=(
                        f"Created an ordered plan with "
                        f"{len(steps)} steps."
                    )
                )

        # Step 6: Identify natural language application commands.

        pattern = (
            r"^(?:(?:please|can you|could you|would you)\s+)?"
            r"(?:(open|launch|start|run|bring up)\b\s*|"
            r"(?:i want to use|i need to use|"
            r"i would like to use|i would like|"
            r"i want|i need)\s+)"
            r"(.*)$"
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

        # Step 7: Handle missing application name.

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

        # Step 8: Get installed application catalogue.

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

        # Step 9: Match application names, IDs and aliases.

        matches = self._match_application(
            application,
            installed_apps
        )

        if not matches:
            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(application=application),
                steps=[],
                requires_clarification=False,
                clarification_question=None,
                status="unsupported",
                message="No matching application was found."
            )

        best_match = matches[0]
        best_confidence = best_match["confidence"]

        possible_matches = [
            item for item in matches
            if item["confidence"] >= 0.65
        ]

        # Step 10: Detect genuinely close matches.

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

        # Step 11: Accept high-confidence match.

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

        # Step 12: Ask clarification for medium confidence.

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

        # Step 13: Reject low-confidence match.

        return PlannerResponse(
            intent="open_application",
            entities=CommandEntities(application=application),
            steps=[],
            requires_clarification=False,
            clarification_question=None,
            status="unsupported",
            message=f"{application} is not currently available."
        )
