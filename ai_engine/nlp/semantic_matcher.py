
try:
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    SentenceTransformer = None
    cos_sim = None
    HAS_SENTENCE_TRANSFORMERS = False


class SemanticMatcher:

    def __init__(self):
        if not HAS_SENTENCE_TRANSFORMERS or SentenceTransformer is None:
            self.model = None
            self.intent_embeddings = {}
            return

        self.model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        # Examples for each supported intent
        self.intent_examples = {

            "open_application": [
                "Open an application",
                "Launch an application",
                "Start an application",
                "Run an application",
                "Bring up an application",
                "I want to use an application",
                "Please open Notepad",
                "Can you launch Chrome?"
            ],

            "move_window": [
                "Move the window",
                "Drag the window",
                "Swipe the window",
                "Move this application window",
                "I want to reposition the window",
                "Shift the window to another position"
            ],

            "maximize_window": [
                "Maximize the window",
                "Make it full screen",
                "Expand the window",
                "Make this window bigger",
                "Switch to maximized mode",
                "Show the application in full screen"
            ]
        }

        # Generate embeddings once during initialization
        self.intent_embeddings = {

            intent: self.model.encode(
                examples,
                convert_to_tensor=True
            )

            for intent, examples in self.intent_examples.items()
        }

   
    def predict_intent(self, user_input):

        if not user_input or not user_input.strip():
            return {
                "intent": None,
                "confidence": 0.0,
                "status": "empty_input",
                "message": "Please enter a command."
            }

        if not self.model or not self.intent_embeddings:
            lower = user_input.lower().strip()
            if any(k in lower for k in ["open", "launch", "start", "run"]):
                return {"intent": "open_application", "confidence": 0.9, "status": "recognized", "message": "Matched application command."}
            if any(k in lower for k in ["move", "drag", "shift"]):
                return {"intent": "move_window", "confidence": 0.9, "status": "recognized", "message": "Matched window command."}
            if any(k in lower for k in ["maximize", "full screen", "bigger"]):
                return {"intent": "maximize_window", "confidence": 0.9, "status": "recognized", "message": "Matched window command."}
            return {"intent": None, "confidence": 0.0, "status": "unsupported", "message": "Unsupported command."}

        input_embedding = self.model.encode(
            user_input,
            convert_to_tensor=True
        )

        results = {}

        for intent, embeddings in self.intent_embeddings.items():

            similarity_scores = cos_sim(
                input_embedding,
                embeddings
            )

            results[intent] = float(
                similarity_scores.max().item()
            )

        ranked_results = sorted(
            results.items(),
            key=lambda item: item[1],
            reverse=True
        )

        best_intent, best_score = ranked_results[0]
        second_score = ranked_results[1][1]

        # Initial thresholds; these require further validation
        MIN_CONFIDENCE = 0.65
        MIN_MARGIN = 0.15

        if best_score < MIN_CONFIDENCE:
            return {
                "intent": None,
                "confidence": best_score,
                "all_scores": results,
                "status": "unsupported",
                "message": "I could not understand the command."
            }

        if best_score - second_score < MIN_MARGIN:
            return {
                "intent": None,
                "confidence": best_score,
                "all_scores": results,
                "status": "clarification_required",
                "message": "Could you clarify what action you want?"
            }

        return {
            "intent": best_intent,
            "confidence": best_score,
            "all_scores": results,
            "status": "recognized",
            "message": "Intent recognized successfully."
        }
