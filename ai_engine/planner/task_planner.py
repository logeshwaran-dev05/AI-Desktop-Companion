import re
from difflib import SequenceMatcher
from typing import Optional, Tuple, List, Dict, Any

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
    def normalize(value: str) -> str:
        """Normalize names for application matching."""
        return re.sub(r"\s+", "", (value or "").lower().strip())

    def _match_application(
        self,
        name: str,
        installed_apps: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], float, List[Dict[str, Any]]]:
        """Match an application name or alias against the installed apps catalogue."""
        requested_name = self.normalize(name)
        if not requested_name:
            return None, 0.0, []

    def _match_application(self, application, installed_apps):
        """Find the best matching installed application."""

        requested_name = self.normalize(application)
        matches = []

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

        matches.sort(
            key=lambda item: item["confidence"],
            reverse=True
        )

        best_match = matches[0] if matches else None
        best_confidence = best_match["confidence"] if best_match else 0.0
        possible_matches = [
            item for item in matches
            if item["confidence"] >= 0.70
        ]

        return best_match, best_confidence, possible_matches

    def process_command(self, request: CommandRequest) -> PlannerResponse:
        # Step 1: Normalize input
        raw_text = (request.text or "").strip()
        user_input = " ".join(raw_text.split()).lower()

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

        # Avoid intercepting search commands like "search who is ... on google"
        is_explicit_search = bool(
            re.match(r"^(?:(?:please|can you|could you|would you)\s+)?(?:search|find|look up|play|stream|google)\b", user_input)
        )

        if not is_explicit_search and user_input.startswith(question_words):
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
        installed_apps = get_installed_apps()

        # Step 4: Handle search and playback commands (search_web_app)
        # Check for incomplete / missing search queries first
        missing_query_patterns = [
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:search(?:\s+for)?|find|look up)\s+(?:on|in)\s*(.*)$",
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:play|stream|listen to)\s+(?:on|in)\s*(.*)$",
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:search(?:\s+for)?|find|look up)$",
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:play|stream|listen to)$",
        ]

        for mq_pat in missing_query_patterns:
            mq_match = re.match(mq_pat, user_input)
            if mq_match:
                is_play = "play" in user_input or "stream" in user_input or "listen" in user_input
                action_word = "play" if is_play else "search for"
                return PlannerResponse(
                    intent="search_web_app",
                    entities=CommandEntities(),
                    steps=[],
                    requires_clarification=True,
                    clarification_question=f"What would you like to {action_word}?",
                    status="clarification_required",
                    message="Search query is missing."
                )

        # Targeted play / search patterns with query and service:
        # e.g. "play believer on youtube", "search python tutorials on google"
        search_match = None
        extracted_query = ""
        extracted_target = ""

        # Pattern A: play <query> on/in <service>
        pat_a = re.match(
            r"^(?:(?:please|can you|could you|would you)\s+)?"
            r"(?:play|stream|listen to)\s+(.+?)\s+(?:on|in)\s+(.+)$",
            user_input
        )
        # Pattern B: search (for) <query> on/in <service>
        pat_b = re.match(
            r"^(?:(?:please|can you|could you|would you)\s+)?"
            r"(?:search(?:\s+for)?|find|look up)\s+(.+?)\s+(?:on|in)\s+(.+)$",
            user_input
        )
        # Pattern C: open <service> and/then play <query>
        pat_c = re.match(
            r"^(?:(?:please|can you|could you|would you)\s+)?"
            r"(?:open|launch|start|go to)\s+(.+?)\s+(?:and|then)\s+(?:play|stream|listen to)\s+(.+)$",
            user_input
        )
        # Pattern D: open <service> and/then search (for) <query>
        pat_d = re.match(
            r"^(?:(?:please|can you|could you|would you)\s+)?"
            r"(?:open|launch|start|go to)\s+(.+?)\s+(?:and|then)\s+(?:search(?:\s+for)?|find|look up)\s+(.+)$",
            user_input
        )
        # Pattern E: google <query>
        pat_e = re.match(
            r"^(?:(?:please|can you|could you|would you)\s+)?google\s+(.+)$",
            user_input
        )
        # Pattern F: generic play <query> -> default to youtube
        pat_f = re.match(
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:play|stream|listen to)\s+(.+)$",
            user_input
        )
        # Pattern G: generic search <query> -> default to google
        pat_g = re.match(
            r"^(?:(?:please|can you|could you|would you)\s+)?search(?:\s+for)?\s+(.+)$",
            user_input
        )

        if pat_a:
            extracted_query = pat_a.group(1).strip()
            extracted_target = pat_a.group(2).strip()
            search_match = True
        elif pat_b:
            extracted_query = pat_b.group(1).strip()
            extracted_target = pat_b.group(2).strip()
            search_match = True
        elif pat_c:
            extracted_target = pat_c.group(1).strip()
            extracted_query = pat_c.group(2).strip()
            search_match = True
        elif pat_d:
            extracted_target = pat_d.group(1).strip()
            extracted_query = pat_d.group(2).strip()
            search_match = True
        elif pat_e:
            extracted_query = pat_e.group(1).strip()
            extracted_target = "google"
            search_match = True
        elif pat_f:
            extracted_query = pat_f.group(1).strip()
            extracted_target = "youtube"
            search_match = True
        elif pat_g:
            extracted_query = pat_g.group(1).strip()
            extracted_target = "google"
            search_match = True

        if search_match:
            # Clean up query
            clean_query = extracted_query.rstrip("?.!,")
            if not clean_query:
                return PlannerResponse(
                    intent="search_web_app",
                    entities=CommandEntities(),
                    steps=[],
                    requires_clarification=True,
                    clarification_question="What would you like to search for?",
                    status="clarification_required",
                    message="Search query is missing."
                )

            # Match target against catalogue
            best_match, best_confidence, _ = self._match_application(extracted_target, installed_apps)

            if not best_match or best_confidence < 0.70:
                return PlannerResponse(
                    intent="search_web_app",
                    entities=CommandEntities(
                        application=extracted_target,
                        parameters={"query": clean_query}
                    ),
                    steps=[],
                    requires_clarification=False,
                    clarification_question=None,
                    status="unsupported",
                    message=f"{extracted_target} is not currently available."
                )

            selected_app = best_match["app"]
            app_name = selected_app["app_name"]
            app_id = selected_app["app_id"]

            return PlannerResponse(
                intent="search_web_app",
                entities=CommandEntities(
                    application=app_name,
                    parameters={"query": clean_query}
                ),
                steps=[
                    PlanStep(
                        step_id=1,
                        action="search_web_app",
                        target=app_id,
                        depends_on=[],
                        expected_outcome=f"Search for '{clean_query}' on {app_name}.",
                        parameters={"query": clean_query}
                    )
                ],
                requires_clarification=False,
                clarification_question=None,
                status="plan_ready",
                message=f"Search for '{clean_query}' on {app_name} ready."
            )

        # Step 5: Identify natural language application open commands
        open_pattern = (
            r"^(?:(?:please|can you|could you|would you)\s+)?"
            r"(?:(open|launch|start|run|bring up)\b\s*|"
            r"(?:i want to use|i need to use|"
            r"i would like to use|i would like|"
            r"i want|i need)\s+)"
            r"(.*)$"
        )

        match = re.match(pattern, user_input)
        match = re.match(open_pattern, user_input)

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

        application = match.group(2).strip().rstrip("?.!,")

        # Step 7: Handle missing application name.

        # Step 6: Handle missing application name
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
        # Step 7: Match application against catalogue
        best_match, best_confidence, possible_matches = self._match_application(application, installed_apps)

        if not best_match:
            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(application=application),
                steps=[],
                requires_clarification=False,
                clarification_question=None,
                status="unsupported",
                message=f"{application} is not currently available."
            )

        # Step 10: Detect genuinely close matches.

        # Step 8: Detect genuinely close ambiguous matches
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

        # Step 9: Accept high-confidence match
        if best_confidence >= 0.85:

            selected_app = best_match["app"]
            application_name = selected_app["app_name"]
            app_id = selected_app["app_id"]

            # Use app_id for standard benchmark targets (chrome, spotify, youtube, google),
            # and application_name for standard Windows built-ins (Notepad, Calculator, Paint)
            step_target = app_id if app_id in ("chrome", "spotify", "youtube", "google") else application_name

            return PlannerResponse(
                intent="open_application",
                entities=CommandEntities(
                    application=application_name
                ),
                steps=[
                    PlanStep(
                        step_id=1,
                        action="open_application",
                        target=step_target,
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

        # Step 10: Ask clarification for medium confidence
        if best_confidence >= 0.70:
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

        # Step 11: Reject low-confidence match
        return PlannerResponse(
            intent="open_application",
            entities=CommandEntities(application=application),
            steps=[],
            requires_clarification=False,
            clarification_question=None,
            status="unsupported",
            message=f"{application} is not currently available."
        )
