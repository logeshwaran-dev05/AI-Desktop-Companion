
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
        requires_clarification: Optional[bool] = None,
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
                requires_clarification
                if requires_clarification is not None
                else (status == "clarification_required")
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

        # 2.05 Missing search / play query clarification.
        missing_search = self._try_missing_search_query(text)
        if missing_search is not None:
            return missing_search

        # 2.1 Compound YouTube search + play video plans.
        yt_compound = self._try_youtube_compound_plan(text)
        if yt_compound is not None:
            return yt_compound

        # 2.2 Compound AI assistant prompting (ChatGPT / Gemini / Claude).
        ai_compound = self._try_ai_prompt_plan(text)
        if ai_compound is not None:
            return ai_compound

        # 2.3 Open application and type text (e.g. "open notepad and type hello").
        open_type = self._try_open_and_type_plan(text)
        if open_type is not None:
            return open_type

        # 2.4 Cross-app copy/paste, hotkeys, and direct URL navigation.
        human_utility = self._try_human_utility_plan(text)
        if human_utility is not None:
            return human_utility

        # 2.5 Search and playback commands (e.g. "play believer on youtube", "search python on google")
        search_match = re.search(
            r"^(?:(?:please|can you|could you)\s+)?(?:(play|stream|listen to|search for|search|look up)\s+)(.+?)\s+(?:on|in)\s+([a-zA-Z0-9_\s]+)\s*[?.!]*$",
            text,
            re.IGNORECASE,
        )
        if search_match:
            query = search_match.group(2).strip().rstrip("?.!,")
            platform_name = search_match.group(3).strip().rstrip("?.!,")

            # Resolve platform name
            from ai_engine.catalogue import get_installed_apps
            res_status, record, _ = self._resolve_application(platform_name)
            app_id = None
            app_display = None
            if res_status != "unsupported" and record:
                app_id = record.app_id
                app_id = app_id[4:] if app_id.startswith("app_") else app_id
                app_display = record.display_name
            else:
                # Check AI Engine catalogue (handles web apps like YouTube, Google, Spotify)
                p_norm = platform_name.lower().strip()
                for app in get_installed_apps():
                    candidates = [app["app_name"].lower(), app["app_id"].lower(), *[a.lower() for a in app.get("aliases", [])]]
                    if p_norm in candidates:
                        app_id = app["app_id"]
                        app_display = app["app_name"]
                        break

            if not app_id:
                return self._response(
                    intent="search_web_app",
                    status="unsupported",
                    message=f"No supported application found matching '{platform_name}'.",
                )

            step = PlanStep(
                step_id=1,
                action="search_web_app",
                target=app_id,
                depends_on=[],
                expected_outcome=f"Search for '{query}' on {app_display}.",
                parameters={"query": query},
            )
            return self._response(
                intent="search_web_app",
                status="plan_ready",
                message=f"Search for '{query}' on {app_display} ready.",
                application=app_display,
                parameters={"query": query},
                steps=[step],
            )

        # 3. Extract the requested application.
        target = self._extract_target(text)

        if target is None:
            return self._response(
                intent="unknown",
                status="unsupported",
                message="This command is not currently supported.",
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
        app_name = record.display_name
        if record.app_id in ("app_google_chrome", "app_spotify"):
            step_target = record.app_id
        elif app_name.lower() in ("notepad", "calculator", "paint"):
            step_target = app_name
        else:
            step_target = record.app_id

        step = PlanStep(
            step_id=1,
            action="open_application",
            target=step_target,
            depends_on=[],
            expected_outcome=(
                f"{app_name} is opened successfully."
            ),
            parameters={},
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

    # ---------------------------------------------------------
    # COMPOUND & HUMAN-ACTIVITY PLANNING HELPERS
    # ---------------------------------------------------------

    def _try_missing_search_query(self, text: str) -> Optional[PlannerResponse]:
        """Detect incomplete search/play commands and ask for clarification."""
        lower = text.lower().strip().rstrip("?.!")
        missing_patterns = [
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:search(?:\s+for)?|find|look up)\s+(?:on|in)\s*(.*)$",
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:play|stream|listen to)\s+(?:on|in)\s*(.*)$",
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:search(?:\s+for)?|find|look up)$",
            r"^(?:(?:please|can you|could you|would you)\s+)?(?:play|stream|listen to)$",
        ]
        for pat in missing_patterns:
            if re.match(pat, lower):
                is_play = any(w in lower for w in ("play", "stream", "listen"))
                action_word = "play" if is_play else "search for"
                return self._response(
                    intent="search_web_app",
                    status="clarification_required",
                    message="Search query is missing.",
                    clarification_question=f"What would you like to {action_word}?",
                )
        return None

    def _try_youtube_compound_plan(self, text: str) -> Optional[PlannerResponse]:
        """
        Handle multi-step YouTube commands such as:
        - "Open YouTube, search for lofi hip hop, and play the second video"
        - "Open YouTube using my Boovi Chrome profile, search for music, and play the second video"
        - "Open YouTube and play a video"
        - "play believer on youtube and click the 2nd video"
        """
        lower = text.lower().strip()
        if "youtube" not in lower and "yt" not in lower.split():
            return None

        # Clarification when user says "play a video" without specifying which result
        if re.search(r"\bplay\s+(?:a|any|some)\s+video\b", lower):
            return self._response(
                intent="multi_step",
                status="clarification_required",
                message="Video selection number is missing.",
                clarification_question="Which video would you like me to play (e.g., first, second, or third video)?",
                application="youtube",
            )

        # Extract ordinal video index (0-based for planner contract)
        ordinal_map = {
            "first": 0, "1st": 0, "1": 0, "one": 0,
            "second": 1, "2nd": 1, "2": 1, "two": 1,
            "third": 2, "3rd": 2, "3": 2, "three": 2,
            "fourth": 3, "4th": 3, "4": 3, "four": 3,
            "fifth": 4, "5th": 4, "5": 4, "five": 4,
        }
        ordinal_match = re.search(
            r"(?:and\s+)?(?:play|click|open)\s+(?:the\s+)?(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|\d+)\s+(?:video|result)",
            lower,
        )
        if not ordinal_match:
            return None

        ord_token = ordinal_match.group(1).strip()
        video_index = ordinal_map.get(ord_token, max(0, int(ord_token) - 1) if ord_token.isdigit() else 0)

        # Extract Chrome profile if mentioned
        profile_name: Optional[str] = None
        profile_directory: Optional[str] = None
        prof_match = re.search(
            r"(?:using|with)\s+(?:my\s+)?([a-zA-Z0-9_\s]+?)\s+(?:chrome\s+)?profile",
            text,
            re.IGNORECASE,
        )
        if prof_match:
            profile_name = prof_match.group(1).strip()
            profile_directory = "Default"

        # Extract search query
        search_query = ""
        sq_match = re.search(
            r"search\s+(?:for\s+)?(.+?)(?:\s*,?\s*(?:and\s+)?(?:play|click|open)\s+(?:the\s+)?(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|\d+))",
            text,
            re.IGNORECASE,
        )
        if sq_match:
            search_query = sq_match.group(1).strip().rstrip(",")
        else:
            play_sq_match = re.search(
                r"^(?:play|stream)\s+(.+?)\s+on\s+(?:youtube|yt)\b",
                text,
                re.IGNORECASE,
            )
            if play_sq_match:
                search_query = play_sq_match.group(1).strip()

        if not search_query:
            return None

        params: dict = {
            "search_query": search_query,
            "video_index": video_index,
        }
        if profile_name:
            params["profile_name"] = profile_name
            params["profile_directory"] = profile_directory

        step1_params = {}
        if profile_directory:
            step1_params["profile_dir"] = profile_directory
            step1_params["profile_name"] = profile_name

        steps = [
            PlanStep(
                step_id=1,
                action="open_website",
                target="youtube",
                depends_on=[],
                expected_outcome="YouTube is opened in the browser.",
                parameters=step1_params,
            ),
            PlanStep(
                step_id=2,
                action="search",
                target=search_query,
                depends_on=[1],
                expected_outcome=f"Search YouTube for '{search_query}'.",
                parameters={"query": search_query, "platform": "youtube"},
            ),
            PlanStep(
                step_id=3,
                action="play_video",
                target=str(video_index),
                depends_on=[2],
                expected_outcome=f"Play video #{video_index + 1} from YouTube search results.",
                parameters={"ordinal_index": video_index + 1},
            ),
        ]

        return self._response(
            intent="multi_step",
            status="plan_ready",
            message=f"Multi-step YouTube plan ready for '{search_query}'.",
            application="youtube",
            parameters=params,
            steps=steps,
        )

    def _try_ai_prompt_plan(self, text: str) -> Optional[PlannerResponse]:
        """
        Handle AI web assistant prompting commands such as:
        - "Open ChatGPT and ask explain artificial intelligence"
        - "ask gpt to write an email to my manager"
        - "open gemini and type write a python script"
        - "ask chatgpt write a leave letter and paste in notepad"
        """
        ai_patterns = [
            r"^(?:(?:please|can you|could you)\s+)?(?:open|launch|start)\s+(chatgpt|chat\s*gpt|gpt|gemini|google\s*gemini|claude)\s+and\s+(?:ask|type|prompt|write|tell(?:\s+it)?(?:\s+to)?)\s+(.+)$",
            r"^(?:(?:please|can you|could you)\s+)?(?:ask|tell|prompt)\s+(chatgpt|chat\s*gpt|gpt|gemini|google\s*gemini|claude)\s+(?:to\s+)?(.+)$",
        ]
        matched = None
        for pat in ai_patterns:
            m = re.match(pat, text, re.IGNORECASE)
            if m:
                matched = m
                break

        if not matched:
            return None

        raw_ai = matched.group(1).strip().lower()
        prompt = matched.group(2).strip().rstrip("?.!")

        if "gemini" in raw_ai:
            ai_id, ai_display = "gemini", "Google Gemini"
        elif "claude" in raw_ai:
            ai_id, ai_display = "claude", "Claude"
        else:
            ai_id, ai_display = "chatgpt", "ChatGPT"

        # Optional chained paste destination: "... and paste in notepad"
        dest_app = None
        paste_match = re.search(
            r"\s+and\s+paste\s+(?:it\s+)?(?:in|into|to)\s+([a-zA-Z0-9_\s]+)$",
            prompt,
            re.IGNORECASE,
        )
        if paste_match:
            dest_app = paste_match.group(1).strip()
            prompt = prompt[:paste_match.start()].strip()

        is_email_task = bool(re.search(r"\b(e-?mail|mail|gmail)\b", prompt, re.IGNORECASE))
        email_addr_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", prompt)
        recipient_email = email_addr_match.group(0) if email_addr_match else None

        steps = [
            PlanStep(
                step_id=1,
                action="open_website",
                target=ai_id,
                depends_on=[],
                expected_outcome=f"{ai_display} is opened in the browser.",
                parameters={},
            ),
            PlanStep(
                step_id=2,
                action="ask_prompt",
                target=prompt,
                depends_on=[1],
                expected_outcome=f"Type and submit prompt to {ai_display}.",
                parameters={
                    "prompt": prompt,
                    "text": prompt,
                    "ai_app": ai_display,
                    "press_enter": True,
                    "delay_before_type": 2.0,
                },
            ),
        ]

        requires_clarification = False
        clarification_question = None

        if dest_app:
            steps.append(
                PlanStep(
                    step_id=3,
                    action="capture_ai_response",
                    target=ai_display,
                    depends_on=[2],
                    expected_outcome=f"Capture generated response from {ai_display}.",
                    parameters={"delay_before_capture": 6.0},
                )
            )
            steps.append(
                PlanStep(
                    step_id=4,
                    action="clipboard_paste",
                    target=dest_app,
                    depends_on=[3],
                    expected_outcome=f"Paste captured response into {dest_app}.",
                    parameters={},
                )
            )
        elif is_email_task:
            steps.append(
                PlanStep(
                    step_id=3,
                    action="capture_ai_response",
                    target=ai_display,
                    depends_on=[2],
                    expected_outcome=f"Copy drafted email from {ai_display}.",
                    parameters={"delay_before_capture": 6.0},
                )
            )
            steps.append(
                PlanStep(
                    step_id=4,
                    action="open_website",
                    target="gmail",
                    depends_on=[3],
                    expected_outcome="Open Gmail to compose the email.",
                    parameters={},
                )
            )
            steps.append(
                PlanStep(
                    step_id=5,
                    action="clipboard_paste",
                    target="Gmail",
                    depends_on=[4],
                    expected_outcome="Paste drafted email body into Gmail.",
                    parameters={"delay_before_paste": 2.0},
                )
            )
            if recipient_email:
                steps.append(
                    PlanStep(
                        step_id=6,
                        action="compose_email",
                        target=recipient_email,
                        depends_on=[5],
                        expected_outcome=f"Address email to {recipient_email}.",
                        parameters={"to": recipient_email},
                    )
                )
            else:
                requires_clarification = True
                clarification_question = (
                    f"I've drafted the email with {ai_display}, copied it, and opened Gmail to paste it — "
                    "to whom should I send this email? (Please provide the recipient's email address.)"
                )

        return self._response(
            intent="multi_step",
            status="plan_ready",
            message=f"Multi-step {ai_display} prompt plan ready.",
            application=ai_display,
            parameters={"prompt": prompt, **({"recipient": recipient_email} if recipient_email else {})},
            steps=steps,
            requires_clarification=requires_clarification,
            clarification_question=clarification_question,
        )

    def _try_open_and_type_plan(self, text: str) -> Optional[PlannerResponse]:
        """Handle 'open <app> and type/write <text>' day-to-day workflow."""
        m = re.match(
            r"^(?:(?:please|can you|could you)\s+)?(?:open|launch|start)\s+([a-zA-Z0-9_\s]+?)\s+and\s+(?:type|write|enter)\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if not m:
            return None

        app_query = m.group(1).strip()
        content = m.group(2).strip()
        res_status, record, _ = self._resolve_application(app_query)
        if res_status != "resolved" or record is None:
            return None

        app_name = record.display_name
        step_target = app_name if app_name.lower() in ("notepad", "calculator", "paint") else record.app_id

        steps = [
            PlanStep(
                step_id=1,
                action="open_application",
                target=step_target,
                depends_on=[],
                expected_outcome=f"{app_name} is opened.",
                parameters={},
            ),
            PlanStep(
                step_id=2,
                action="type_text",
                target=app_name,
                depends_on=[1],
                expected_outcome=f"Type text into {app_name}.",
                parameters={"text": content, "press_enter": False, "delay_before_type": 2.0},
            ),
        ]

        return self._response(
            intent="multi_step",
            status="plan_ready",
            message=f"Multi-step open and type plan ready for {app_name}.",
            application=app_name,
            parameters={"text": content},
            steps=steps,
        )

    def _try_human_utility_plan(self, text: str) -> Optional[PlannerResponse]:
        """Handle everyday copy/paste, hotkey, and direct URL navigation commands."""
        # 1. Cross-app copy & paste: "copy from <app1> and paste in <app2>"
        cp_match = re.match(
            r"^copy\s+(?:from\s+([a-zA-Z0-9_\s]+?)\s+)?and\s+paste\s+(?:in|into|to)\s+([a-zA-Z0-9_\s]+)$",
            text,
            re.IGNORECASE,
        )
        if cp_match:
            src = (cp_match.group(1) or "active_window").strip()
            dst = cp_match.group(2).strip()
            steps = [
                PlanStep(
                    step_id=1,
                    action="clipboard_copy",
                    target=src,
                    depends_on=[],
                    expected_outcome=f"Copy selection from {src}.",
                    parameters={},
                ),
                PlanStep(
                    step_id=2,
                    action="clipboard_paste",
                    target=dst,
                    depends_on=[1],
                    expected_outcome=f"Paste copied text into {dst}.",
                    parameters={},
                ),
            ]
            return self._response(
                intent="multi_step",
                status="plan_ready",
                message=f"Copy from {src} and paste into {dst} ready.",
                application=dst,
                steps=steps,
            )

        # 2. Direct clipboard copy / paste
        if re.match(r"^(?:copy|copy\s+(?:this|text|selection))$", text, re.IGNORECASE):
            return self._response(
                intent="clipboard_copy",
                status="plan_ready",
                message="Clipboard copy ready.",
                steps=[
                    PlanStep(
                        step_id=1,
                        action="clipboard_copy",
                        target="active_window",
                        depends_on=[],
                        expected_outcome="Copy selected content to clipboard.",
                        parameters={},
                    )
                ],
            )

        paste_only = re.match(
            r"^paste(?:\s+(?:in|into|to)\s+([a-zA-Z0-9_\s]+))?$",
            text,
            re.IGNORECASE,
        )
        if paste_only:
            dst = (paste_only.group(1) or "active_window").strip()
            return self._response(
                intent="clipboard_paste",
                status="plan_ready",
                message=f"Clipboard paste into {dst} ready.",
                application=dst if dst != "active_window" else None,
                steps=[
                    PlanStep(
                        step_id=1,
                        action="clipboard_paste",
                        target=dst,
                        depends_on=[],
                        expected_outcome=f"Paste clipboard content into {dst}.",
                        parameters={},
                    )
                ],
            )

        # 3. Keyboard hotkey: "press ctrl+c" / "hit alt+tab"
        hk_match = re.match(r"^(?:press|hit)\s+([a-zA-Z0-9_+\-\s]+)$", text, re.IGNORECASE)
        if hk_match:
            raw_keys = hk_match.group(1).strip().lower()
            keys = [k.strip() for k in re.split(r"[+\s]+", raw_keys) if k.strip()]
            if keys:
                return self._response(
                    intent="press_hotkey",
                    status="plan_ready",
                    message=f"Hotkey {'+'.join(keys)} ready.",
                    steps=[
                        PlanStep(
                            step_id=1,
                            action="press_hotkey",
                            target="active_window",
                            depends_on=[],
                            expected_outcome=f"Press hotkey {'+'.join(keys)}.",
                            parameters={"keys": keys},
                        )
                    ],
                )

        # 4. Direct URL navigation: "go to github.com" / "open https://..."
        url_match = re.match(
            r"^(?:go\s+to|visit|navigate\s+to|open)\s+(https?://\S+|[a-zA-Z0-9.-]+\.(?:com|org|net|io|ai|dev|in|edu|gov)(?:/\S*)?)$",
            text,
            re.IGNORECASE,
        )
        if url_match:
            raw_url = url_match.group(1).strip()
            full_url = raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"
            return self._response(
                intent="navigate_url",
                status="plan_ready",
                message=f"Navigate to {full_url} ready.",
                parameters={"url": full_url},
                steps=[
                    PlanStep(
                        step_id=1,
                        action="navigate_url",
                        target=full_url,
                        depends_on=[],
                        expected_outcome=f"Open {full_url} in browser.",
                        parameters={"url": full_url},
                    )
                ],
            )

        # 5. Loop / Batch Resource Downloads:
        dl_match = re.match(
            r"^(?:(?:please|can you|could you)\s+)?(?:loop\s+download|batch\s+download|download\s+all|download\s+resources?)\s*:?\s*(.*)$",
            text,
            re.IGNORECASE,
        )
        if dl_match:
            raw_items = dl_match.group(1).strip().rstrip("?.!")
            raw_items = re.sub(r"\s+(?:one by one|for me|automatically)$", "", raw_items, flags=re.IGNORECASE).strip()
            if not raw_items or raw_items.lower() in ("files", "resources", "links", "them"):
                return self._response(
                    intent="batch_download",
                    status="clarification_required",
                    message="Download items or URLs are missing.",
                    clarification_question="Which files, URLs, or resources would you like me to download in a loop?",
                )
            items = [i.strip() for i in re.split(r"[,;\n]+|\s+and\s+", raw_items) if i.strip()]
            return self._response(
                intent="batch_download",
                status="plan_ready",
                message=f"Loop download plan ready for {len(items)} resource(s).",
                parameters={"items": items},
                steps=[
                    PlanStep(
                        step_id=1,
                        action="batch_download",
                        target="Downloads",
                        depends_on=[],
                        expected_outcome=f"Loop through and download/open {len(items)} resource(s) into Downloads.",
                        parameters={"items": items},
                    )
                ],
            )

        # 6. Standalone Email Composition: "send an email [to <addr>]" / "write an email"
        email_match = re.match(
            r"^(?:(?:please|can you|could you)\s+)?(?:send|write|compose|draft)\s+(?:an?\s+)?e-?mail(?:\s+to\s+(.+))?$",
            text,
            re.IGNORECASE,
        )
        if email_match:
            recipient_part = (email_match.group(1) or "").strip()
            addr_m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", recipient_part)
            if not addr_m:
                return self._response(
                    intent="compose_email",
                    status="clarification_required",
                    message="Recipient email address is needed.",
                    application="Gmail",
                    clarification_question="To whom should I send this email? (Please provide their email address and what you'd like it to say.)",
                    steps=[
                        PlanStep(
                            step_id=1,
                            action="open_website",
                            target="gmail",
                            depends_on=[],
                            expected_outcome="Open Gmail while awaiting recipient details.",
                            parameters={},
                        )
                    ],
                )
            to_addr = addr_m.group(0)
            return self._response(
                intent="compose_email",
                status="plan_ready",
                message=f"Email composition ready for {to_addr}.",
                application="Gmail",
                parameters={"to": to_addr},
                steps=[
                    PlanStep(
                        step_id=1,
                        action="open_website",
                        target="gmail",
                        depends_on=[],
                        expected_outcome="Open Gmail.",
                        parameters={},
                    ),
                    PlanStep(
                        step_id=2,
                        action="compose_email",
                        target=to_addr,
                        depends_on=[1],
                        expected_outcome=f"Compose email to {to_addr}.",
                        parameters={"to": to_addr},
                    ),
                ],
            )

        # 7. WhatsApp Messaging: "message <person> on whatsapp saying <msg>"
        wa_match = re.match(
            r"^(?:(?:please|can you|could you)\s+)?(?:message|text|send\s+(?:a\s+)?(?:whatsapp\s+)?message\s+to)\s+(.+?)\s+on\s+whatsapp(?:\s+(?:saying|that|:)\s+(.+))?$",
            text,
            re.IGNORECASE,
        )
        if wa_match:
            person = wa_match.group(1).strip()
            msg = (wa_match.group(2) or "").strip()
            if not msg:
                return self._response(
                    intent="multi_step",
                    status="clarification_required",
                    message="WhatsApp message text is missing.",
                    application="WhatsApp",
                    clarification_question=f"What message would you like me to send to {person} on WhatsApp?",
                )
            return self._response(
                intent="multi_step",
                status="plan_ready",
                message=f"WhatsApp message plan ready for {person}.",
                application="WhatsApp",
                parameters={"recipient": person, "text": msg},
                steps=[
                    PlanStep(
                        step_id=1,
                        action="open_application",
                        target="whatsapp",
                        depends_on=[],
                        expected_outcome="Open WhatsApp.",
                        parameters={},
                    ),
                    PlanStep(
                        step_id=2,
                        action="type_text",
                        target="WhatsApp",
                        depends_on=[1],
                        expected_outcome=f"Type message to {person}.",
                        parameters={"text": msg, "press_enter": True, "delay_before_type": 2.0},
                    ),
                ],
            )

        return None
