
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
            ]
        }

    def extract_entities(self, user_input, intent):

        text = user_input.lower().strip()

        entities = {
            "action": None,
            "application": None,
            "target": None
        }

        if intent == "open_application":

            entities["action"] = "launch"

            for app_id, aliases in self.application_aliases.items():

                for alias in aliases:

                    if alias in text:
                        entities["application"] = app_id
                        break

                if entities["application"]:
                    break

        elif intent == "move_window":

            entities["action"] = "move"
            entities["target"] = "window"

        elif intent == "maximize_window":

            entities["action"] = "maximize"
            entities["target"] = "window"

        return entities
