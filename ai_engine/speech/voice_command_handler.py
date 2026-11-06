
from ai_engine.speech.speech_to_text import SpeechToText
from ai_engine.planner.task_planner import TaskPlanner
from ai_engine.schemas.command_schema import CommandRequest


class VoiceCommandHandler:

    def __init__(self):
        self.speech_to_text = SpeechToText()
        self.task_planner = TaskPlanner()

    def process_audio(self, audio_path, language=None):

        # Step 1: Convert audio into text
        transcription = self.speech_to_text.transcribe_audio(
            audio_path,
            language=language
        )

        recognized_text = transcription["text"]

        # Step 2: Handle empty transcription
        if not recognized_text.strip():
            return {
                "transcription": transcription,
                "planner_response": None,
                "message": "No speech was recognized."
            }

        # Step 3: Create a voice command request
        request = CommandRequest(
            text=recognized_text,
            input_type="voice",
            language=transcription["language"]
        )

        # Step 4: Send the request to TaskPlanner
        planner_response = self.task_planner.process_command(request)

        # Step 5: Return both results
        return {
            "transcription": transcription,
            "planner_response": planner_response,
            "message": "Voice command processed successfully."
        }
