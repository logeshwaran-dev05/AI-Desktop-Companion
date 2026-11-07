
from faster_whisper import WhisperModel


class SpeechToText:
    def __init__(
        self,
        model_size="small",
        device="cpu",
        compute_type="int8"
    ):
        """Initialize the Faster-Whisper model."""

        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type
        )

    def transcribe_audio(self, audio_path, language=None):
        """Convert an audio file into text."""

        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True
        )

        transcription = " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

        return {
            "text": transcription,
            "language": info.language,
            "language_probability": info.language_probability
        }
