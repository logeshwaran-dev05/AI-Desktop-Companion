
from ai_engine.nlp.semantic_matcher import SemanticMatcher
from ai_engine.nlp.entity_extractor import EntityExtractor


class CommandUnderstanding:

    def __init__(self):
        self.matcher = SemanticMatcher()
        self.extractor = EntityExtractor()

    def understand(self, user_input):

        # Step 1: Identify the user's intent
        prediction = self.matcher.predict_intent(user_input)

        # Step 2: Stop if the intent is unclear or unsupported
        if prediction["status"] != "recognized":
            return {
                "intent": None,
                "entities": {},
                "confidence": prediction["confidence"],
                "status": prediction["status"],
                "message": prediction["message"]
            }

        intent = prediction["intent"]

        # Step 3: Extract action and parameters
        entities = self.extractor.extract_entities(
            user_input,
            intent
        )

        # Step 4: Check whether an application was identified
        if intent == "open_application" and not entities["application"]:
            return {
                "intent": intent,
                "entities": entities,
                "confidence": prediction["confidence"],
                "status": "clarification_required",
                "message": "Which application would you like to open?"
            }

        # Step 5: Return structured understanding
        return {
            "intent": intent,
            "entities": entities,
            "confidence": prediction["confidence"],
            "status": "recognized",
            "message": "Command understood successfully."
        }
