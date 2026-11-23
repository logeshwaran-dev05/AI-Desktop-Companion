
import re

from windows_automation.browser_profiles import (
    resolve_profile_directory
)

from ai_engine.catalogue import (
    get_installed_apps,
    get_supported_websites
)


class EntityExtractor:

    def __init__(self):

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

    def _match_application(self, text):
        """
        Dynamically identify desktop applications
        and supported websites using their catalogues.
        """

        catalogues = [
            get_installed_apps(),
            get_supported_websites()
        ]

        matches = []

        for catalogue in catalogues:

            for app in catalogue:

                candidates = [
                    app["app_name"],
                    app["app_id"],
                    *app.get("aliases", [])
                ]

                for candidate in candidates:

                    candidate = candidate.strip().lower()

                    if not candidate:
                        continue

                    pattern = (
                        r"(?<!\w)"
                        + re.escape(candidate)
                        + r"(?!\w)"
                    )

                    if re.search(pattern, text):
                        matches.append(
                            (len(candidate), app["app_id"])
                        )

        # Prefer the longest matching application name.
        if matches:
            matches.sort(
                key=lambda item: item[0],
                reverse=True
            )

            return matches[0][1]

        return None

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

        # 1. Extract Chrome profile name.

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

        # Remove profile description before application detection.

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

        # 2. Dynamically extract application or website.

        entities["application"] = self._match_application(
            app_search_text
        )

        # 3. Extract ordinal.

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

        # 4. Extract prompt after "ask".

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

        # 5. Extract search query.

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

        # 6. Determine action from intent.

        if intent == "open_application":

            entities["action"] = "launch"

        elif intent == "move_window":

            entities["action"] = "move"
            entities["target"] = "window"

        elif intent == "maximize_window":

            entities["action"] = "maximize"
            entities["target"] = "window"

        return entities
