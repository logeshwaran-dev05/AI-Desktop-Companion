
import re

from windows_automation.browser_profiles import (
    resolve_profile_directory
)


class EntityExtractor:

    def __init__(self):

        self.application_aliases = {
            "notepad": ["notepad", "note pad", "text editor"],
            "calculator": ["calculator", "calc"],
            "chrome": ["chrome", "google chrome"],
            "edge": ["edge", "microsoft edge"],
            "paint": ["paint", "ms paint"],
            "vscode": [
                "vs code",
                "visual studio code",
                "vscode"
            ],
            "chatgpt": ["chatgpt", "chat gpt"],
            "youtube": ["youtube", "you tube"]
        }

        self.ordinal_map = {
            "first": 0,
            "1st": 0,
            "second": 1,
            "2nd": 1,
            "third": 2,
            "3rd": 2,
            "fourth": 3,
            "4th": 3,
            "fifth": 4,
            "5th": 4
        }

    def extract_entities(self, user_input, intent=None):

        text = user_input.strip()
        lower_text = text.lower()

        entities = {
            "action": None,
            "application": None,
            "target": None,
            "ordinal": None,
            "video_index": None,
            "prompt": None,
            "search_query": None,
            "profile_name": None,
            "profile_directory": None
        }

        # 1. Extract Chrome profile name

        profile_pattern = (
            r"\b(?:using|on|with)\s+(?:my\s+)?"
            r"(.+?)\s+(?:chrome\s+)?"
            r"(?:profile|account)\b"
        )

        profile_match = re.search(
            profile_pattern,
            text,
            re.IGNORECASE
        )

        if not profile_match:
            profile_match = re.search(
                r"\b(?:using|on)\s+(?:my\s+)?"
                r"([A-Za-z0-9_-]+)\b"
                r"(?=\s*(?:,|$))",
                text,
                re.IGNORECASE
            )

        # Remove the profile description before app detection.
        app_search_text = lower_text

        if profile_match:
            profile_name = profile_match.group(1).strip()

            entities["profile_name"] = profile_name

            entities["profile_directory"] = (
                resolve_profile_directory(
                    browser="chrome",
                    requested_profile=profile_name
                )
            )

            app_search_text = (
                lower_text[:profile_match.start()]
                + lower_text[profile_match.end():]
            )

        # 2. Extract application

        for app_id, aliases in self.application_aliases.items():

            for alias in aliases:

                pattern = (
                    r"(?<!\w)"
                    + re.escape(alias)
                    + r"(?!\w)"
                )

                if re.search(pattern, app_search_text):

                    entities["application"] = app_id
                    break

            if entities["application"]:
                break

        # 3. Extract ordinal (first, second, 1st, 2nd, etc.)

        ordinal_pattern = (
            r"\b(first|1st|second|2nd|third|3rd|"
            r"fourth|4th|fifth|5th)\b"
        )

        ordinal_match = re.search(
            ordinal_pattern,
            lower_text
        )

        if ordinal_match:

            index = self.ordinal_map[
                ordinal_match.group(1)
            ]

            entities["ordinal"] = index
            entities["video_index"] = index

        # 4. Extract prompt after "ask"

        prompt_match = re.search(
            r"""\bask\s+["'](.+?)["']""",
            text,
            re.IGNORECASE
        )

        if not prompt_match:

            prompt_match = re.search(
                r"\bask\s+(.+?)(?=,\s*(?:and\s+)?"
                r"(?:copy|paste)\b|$)",
                text,
                re.IGNORECASE
            )

        if prompt_match:

            entities["prompt"] = (
                prompt_match.group(1).strip()
            )

        # 5. Extract search query

        search_match = re.search(
            r"""\b(?:search\s+for|look\s+for|find)\s+"""
            r"""["']?(.+?)["']?"""
            r"""(?=,\s*(?:and\s+)?"""
            r"""(?:play|click|open|copy|paste)\b|$)""",
            text,
            re.IGNORECASE
        )

        if search_match:

            entities["search_query"] = (
                search_match.group(1).strip().strip("\"'")
            )

        # 6. Determine action from intent

        if intent == "open_application":

            entities["action"] = "launch"

        elif intent == "move_window":

            entities["action"] = "move"
            entities["target"] = "window"

        elif intent == "maximize_window":

            entities["action"] = "maximize"
            entities["target"] = "window"

        return entities
