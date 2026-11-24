
import re
from typing import Any, TypeAlias

from windows_automation.adapter import WindowsAutomationAdapter
from windows_automation.browser_profiles import resolve_profile_directory


EntityValue: TypeAlias = str | int | None
EntityDictionary: TypeAlias = dict[str, Any]


class EntityExtractor:
    """
    Extract entities from user commands using the dynamically
    discovered Windows Automation application catalogue.
    """

    _default_adapter: WindowsAutomationAdapter | None = None

    def __init__(
        self,
        adapter: WindowsAutomationAdapter | None = None,
    ) -> None:
        if adapter is not None:
            self.adapter = adapter
        else:
            if EntityExtractor._default_adapter is None:
                EntityExtractor._default_adapter = (
                    WindowsAutomationAdapter(auto_discover=True)
                )

            self.adapter = EntityExtractor._default_adapter

        # Ordinal values are zero-based.
        self.ordinal_map: dict[str, int] = {
            "first": 0,
            "1st": 0,
            "second": 1,
            "2nd": 1,
            "third": 2,
            "3rd": 2,
            "fourth": 3,
            "4th": 3,
            "fifth": 4,
            "5th": 4,
        }

    # ---------------------------------------------------------
    # TEXT NORMALIZATION
    # ---------------------------------------------------------

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent matching."""

        text = text.casefold().strip()
        text = text.replace("_", " ")
        text = text.replace("-", " ")
        text = re.sub(r"\s+", " ", text)

        return text

    # ---------------------------------------------------------
    # APPLICATION MATCHING
    # ---------------------------------------------------------

    def _match_application(self, text: str) -> str | None:
        """
        Match applications using dynamically discovered catalogue records.

        Returns a useful application name rather than an internal ID.
        Handles abbreviated aliases generically.
        """

        catalogue = self.adapter.get_catalogue()
        records = catalogue.get_all()
        normalized_text = self._normalize_text(text)

        matches: list[tuple[str, str, str]] = []

        for record in records:
            candidates = [
                (record.display_name, "display"),
                *[
                    (alias, "alias")
                    for alias in (record.aliases or [])
                ],
            ]

            for candidate, candidate_type in candidates:
                if not isinstance(candidate, str):
                    continue

                normalized_candidate = self._normalize_text(candidate)

                if not normalized_candidate:
                    continue

                pattern = (
                    r"(?<!\w)"
                    + re.escape(normalized_candidate)
                    + r"(?!\w)"
                )

                if re.search(pattern, normalized_text):
                    matches.append(
                        (
                            record.app_id,
                            normalized_candidate,
                            candidate_type,
                        )
                    )

        if not matches:
            return None

        # Identify the applications represented by the matches.
        matching_app_ids = {
            match[0] for match in matches
        }

        # Avoid arbitrarily selecting between different applications.
        if len(matching_app_ids) != 1:
            return None

        # Prefer the shortest matching alias for the same application.
        aliases = [
            match[1]
            for match in matches
            if match[2] == "alias"
        ]

        if aliases:
            selected = min(
                aliases,
                key=lambda value: (len(value), value),
            )
        else:
            selected = min(
                (match[1] for match in matches),
                key=lambda value: (len(value), value),
            )

        matching_record = next(
            record
            for record in records
            if record.app_id in matching_app_ids
        )

        canonical_name = self._normalize_text(
            matching_record.display_name
        )

        # Expand an abbreviated alias when it is a prefix
        # of the canonical application name.
        if (
            selected != canonical_name
            and canonical_name.startswith(selected)
        ):
            return canonical_name

        return selected

    # ---------------------------------------------------------
    # URL EXTRACTION
    # ---------------------------------------------------------

    def _extract_url(self, text: str) -> str | None:
        """Extract an explicitly provided URL."""

        pattern = r"""(?:https?://|www\.)[^\s<>"']+"""

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if not match:
            return None

        url = match.group(0).rstrip(".,!?;:)")

        if url.casefold().startswith("www."):
            url = "https://" + url

        return url

    # ---------------------------------------------------------
    # FILE PATH EXTRACTION
    # ---------------------------------------------------------

    def _extract_file_path(self, text: str) -> str | None:
        """Extract a quoted or Windows-style file path."""

        # Check for a quoted path first.
        quoted_pattern = r"""["']([^"']+)["']"""

        quoted_match = re.search(
            quoted_pattern,
            text,
        )

        if quoted_match:
            candidate = quoted_match.group(1).strip()

            if (
                "\\" in candidate
                or "/" in candidate
                or re.search(
                    r"\.[a-zA-Z0-9]{1,8}$",
                    candidate,
                )
            ):
                return candidate

        # Check for a Windows drive path.
        windows_pattern = (
            r"[A-Za-z]:\\"
            r"(?:[^<>:\"|?*\r\n]+\\)*"
            r"[^<>:\"|?*\r\n]*"
        )

        windows_match = re.search(
            windows_pattern,
            text,
        )

        if windows_match:
            return windows_match.group(0).rstrip(".,!?;")

        return None

    # ---------------------------------------------------------
    # ORDINAL EXTRACTION
    # ---------------------------------------------------------

    def _extract_ordinal(self, text: str) -> int | None:
        """Extract ordinal values such as first, second or 2nd."""

        normalized_text = self._normalize_text(text)

        for word, index in self.ordinal_map.items():
            pattern = (
                r"(?<!\w)"
                + re.escape(word)
                + r"(?!\w)"
            )

            if re.search(pattern, normalized_text):
                return index

        return None

    # ---------------------------------------------------------
    # PROMPT EXTRACTION
    # ---------------------------------------------------------

    def _extract_prompt(self, text: str) -> str | None:
        """Extract a prompt following a generic ask/tell phrase."""

        patterns = [
            r"\bask\s+(?:the\s+)?[\w-]+\s+to\s+(.+)",
            r"\bask\s+it\s+to\s+(.+)",
            r"\bask\s+(.+)",
            r"\btell\s+(?:it\s+)?(?:to\s+)?(.+)",
            r"\bprompt\s*[:=]\s*(.+)",
            r"\bwrite\s+(.+)",
            r"\bexplain\s+(.+)",
            r"\bgenerate\s+(.+)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:
                prompt = match.group(1).strip()

                if prompt:
                    return prompt

        return None

    # ---------------------------------------------------------
    # SEARCH QUERY EXTRACTION
    # ---------------------------------------------------------

    def _extract_search_query(self, text: str) -> str | None:
        """Extract the user's search query."""

        patterns = [
            r"\bsearch\s+for\s+(.+)",
            r"\blook\s+up\s+(.+)",
            r"\bfind\s+information\s+about\s+(.+)",
            r"\bsearch\s+(.+)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:
                query = match.group(1).strip()

                # Remove a following play instruction.
                query = re.sub(
                    r"\s+and\s+play\s+.*$",
                    "",
                    query,
                    flags=re.IGNORECASE,
                )

                if query:
                    return query

        return None

    # ---------------------------------------------------------
    # MAIN ENTITY EXTRACTION
    # ---------------------------------------------------------

    def extract_entities(
        self,
        text: str,
        intent: str | None = None,
    ) -> EntityDictionary:
        """
        Extract application, profile, ordinal, prompt, search query,
        URL, file path and action information from a user command.
        """

        if not text or not text.strip():
            result: EntityDictionary = {
                "action": None,
                "application": None,
                "target": None,
                "ordinal": None,
                "video_index": None,
                "prompt": None,
                "search_query": None,
                "profile_name": None,
                "profile_directory": None,
                "url": None,
                "file_path": None,
                "parameters": {},
                "status": "empty_input",
            }

            if intent is not None:
                result["intent"] = intent

            return result

        text = text.strip()
        lower_text = text.casefold()

        entities: EntityDictionary = {
            "action": None,
            "application": None,
            "target": None,
            "ordinal": None,
            "video_index": None,
            "prompt": None,
            "search_query": None,
            "profile_name": None,
            "profile_directory": None,
            "url": None,
            "file_path": None,
            "parameters": {},
            "status": "success",
        }

        # 1. Extract browser profile information.

        profile_pattern = (
            r"\b(?:using|on|with)\s+(?:my\s+)?"
            r"(.+?)\s+(?:chrome\s+)?"
            r"(?:profile|account)\b"
        )

        profile_match = re.search(
            profile_pattern,
            text,
            re.IGNORECASE,
        )

        if not profile_match:
            profile_match = re.search(
                r"\b(?:using|on)\s+(?:my\s+)?"
                r"([A-Za-z0-9_-]+)\b"
                r"(?=\s*(?:,|$))",
                text,
                re.IGNORECASE,
            )

        # Exclude profile description from application matching.
        app_search_text = lower_text

        if profile_match:
            profile_name = profile_match.group(1).strip()

            entities["profile_name"] = profile_name

            entities["profile_directory"] = (
                resolve_profile_directory(
                    browser="chrome",
                    requested_profile=profile_name,
                )
            )

            app_search_text = (
                lower_text[:profile_match.start()]
                + lower_text[profile_match.end():]
            )

        # 2. Extract dynamically discovered application.
        entities["application"] = self._match_application(
            app_search_text
        )

        # 3. Extract ordinal and video index.
        ordinal = self._extract_ordinal(lower_text)

        if ordinal is not None:
            entities["ordinal"] = ordinal
            entities["video_index"] = ordinal

        # 4. Extract prompt.
        entities["prompt"] = self._extract_prompt(text)

        # 5. Extract search query.
        entities["search_query"] = self._extract_search_query(text)

        # 6. Extract URL and file path.
        entities["url"] = self._extract_url(text)
        entities["file_path"] = self._extract_file_path(text)

        # 7. Determine action from the supplied intent.
        if intent == "open_application":
            entities["action"] = "launch"

        elif intent == "move_window":
            entities["action"] = "move"
            entities["target"] = "window"

        elif intent == "maximize_window":
            entities["action"] = "maximize"
            entities["target"] = "window"

        # 8. Collect extracted values into parameters.
        parameters: dict[str, Any] = {}

        for key in (
            "ordinal",
            "prompt",
            "search_query",
            "profile_name",
            "profile_directory",
            "url",
            "file_path",
        ):
            value = entities.get(key)

            if value is not None:
                parameters[key] = value

        entities["parameters"] = parameters

        if intent is not None:
            entities["intent"] = intent

        return entities
