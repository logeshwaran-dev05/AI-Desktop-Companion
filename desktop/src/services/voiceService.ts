/**
 * Voice Interaction Service
 * =========================
 * Manages microphone audio stream, live audio volume metering (via Web Audio API
 * AnalyserNode), and speech-to-text recognition (via Web Speech API SpeechRecognition).
 *
 * Handles:
 * - Permission requests and denied states
 * - Real-time volume level computation for live waveform visualizers
 * - Interim and final transcript collection
 * - Graceful fallback when SpeechRecognition is unavailable in the environment
 * - Thorough cleanup of audio tracks and recognition sessions
 * - Text-to-speech spoken feedback (optional)
 */

export interface VoiceError {
  type:
    | 'not-allowed'
    | 'no-microphone'
    | 'unsupported'
    | 'no-speech'
    | 'network'
    | 'audio-capture'
    | 'unknown';
  message: string;
}

export interface VoiceSessionCallbacks {
  onTranscript: (transcript: string, isFinal: boolean) => void;
  onAudioLevel?: (level: number) => void; // 0 to 100
  onError: (error: VoiceError) => void;
  onNotice?: (message: string) => void;
  onEnd: () => void;
}

// Browser SpeechRecognition interface augmentation
interface IWindowSpeech extends Window {
  SpeechRecognition?: any;
  webkitSpeechRecognition?: any;
}

class VoiceService {
  private activeStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private animFrameId: number | null = null;
  private recognition: any = null;
  private isRecording = false;

  /**
   * Checks whether the current browser / Electron environment supports SpeechRecognition.
   */
  public isRecognitionSupported(): boolean {
    if (typeof window === 'undefined') return false;
    const win = window as IWindowSpeech;
    return Boolean(win.SpeechRecognition || win.webkitSpeechRecognition);
  }

  /**
   * Requests microphone access from the user / system.
   */
  public async requestMicrophoneAccess(): Promise<MediaStream> {
    if (!navigator?.mediaDevices?.getUserMedia) {
      throw new Error('getUserMedia is not supported on this platform.');
    }
    return await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  }

  /**
   * Starts a voice recording session.
   * Connects microphone audio to Web Audio AnalyserNode for live waveform visualizer,
   * and initializes SpeechRecognition if supported.
   */
  public async startListening(callbacks: VoiceSessionCallbacks): Promise<boolean> {
    // Prevent duplicate recording sessions
    if (this.isRecording) {
      console.warn('[VoiceService] Recording is already active. Ignoring start request.');
      return true;
    }

    // 1. Capture microphone stream
    try {
      this.activeStream = await this.requestMicrophoneAccess();
    } catch (err: unknown) {
      const errorObj = err as { name?: string; message?: string };
      if (errorObj.name === 'NotAllowedError' || errorObj.name === 'PermissionDeniedError') {
        callbacks.onError({
          type: 'not-allowed',
          message: 'Microphone permission denied. Please allow microphone access in Windows / browser settings.',
        });
      } else if (errorObj.name === 'NotFoundError' || errorObj.name === 'DevicesNotFoundError') {
        callbacks.onError({
          type: 'no-microphone',
          message: 'No microphone found on this device. Please connect an audio input device.',
        });
      } else {
        callbacks.onError({
          type: 'audio-capture',
          message: errorObj.message || 'Could not access microphone.',
        });
      }
      callbacks.onEnd();
      return false;
    }

    this.isRecording = true;

    // 2. Setup live audio metering for waveform animation
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        this.audioContext = new AudioCtx();
        const source = this.audioContext.createMediaStreamSource(this.activeStream);
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 64;
        source.connect(this.analyser);

        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        const pollAudioLevel = () => {
          if (!this.isRecording || !this.analyser) return;
          this.analyser.getByteFrequencyData(dataArray);

          // Calculate average audio level
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const average = sum / dataArray.length;
          // Normalize to 0-100 scale
          const normalized = Math.min(100, Math.round((average / 128) * 100));

          if (callbacks.onAudioLevel) {
            callbacks.onAudioLevel(normalized);
          }

          this.animFrameId = requestAnimationFrame(pollAudioLevel);
        };

        this.animFrameId = requestAnimationFrame(pollAudioLevel);
      }
    } catch (meterErr) {
      console.warn('[VoiceService] AudioContext metering init skipped:', meterErr);
    }

    // 3. Runtime recognition handling:
    // In Electron, Chromium's built-in Web Speech API delegates to Google Cloud servers
    // without API keys, causing a persistent 'network' error.
    // We seamlessly invoke Windows Native Voice Typing (Win + H) while keeping local Web Audio metering active.
    const isElectronEnv = typeof window !== 'undefined' && Boolean(window.companionAPI?.isElectron);

    if (isElectronEnv) {
      console.log('[VoiceService] Electron runtime detected. Using Windows Voice Typing (Win + H) & local Web Audio meter.');
      if (window.companionAPI?.triggerVoiceTyping) {
        window.companionAPI.triggerVoiceTyping().catch((err) => {
          console.warn('[VoiceService] triggerVoiceTyping error:', err);
        });
      }
      if (callbacks.onNotice) {
        callbacks.onNotice('Windows Voice Typing (Win + H) is active. Speak your command into the prompt.');
      }
      return true;
    }

    // 4. Initialize browser SpeechRecognition if supported (e.g. Chrome / Edge)
    if (!this.isRecognitionSupported()) {
      callbacks.onError({
        type: 'unsupported',
        message: 'Speech recognition engine is not supported in this runtime. You can type commands directly.',
      });
      // We keep audio metering alive so user still sees microphone waveform
      return true;
    }

    try {
      const win = window as IWindowSpeech;
      const SpeechRecognitionConstructor = win.SpeechRecognition || win.webkitSpeechRecognition;
      this.recognition = new SpeechRecognitionConstructor();
      this.recognition.continuous = false;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';

      this.recognition.onstart = () => {
        console.log('[VoiceService] SpeechRecognition session started.');
      };

      this.recognition.onresult = (event: any) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const part = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += part;
          } else {
            interimTranscript += part;
          }
        }

        const text = (finalTranscript || interimTranscript).trim();
        if (text) {
          callbacks.onTranscript(text, Boolean(finalTranscript));
        }
      };

      this.recognition.onerror = (event: any) => {
        console.warn('[VoiceService] SpeechRecognition error:', event.error);
        if (event.error === 'no-speech') {
          callbacks.onError({
            type: 'no-speech',
            message: 'No speech was detected. Please speak clearly into your microphone.',
          });
        } else if (event.error === 'not-allowed') {
          callbacks.onError({
            type: 'not-allowed',
            message: 'Speech recognition permission denied by system.',
          });
        } else if (event.error === 'network') {
          // Fallback notice instead of fatal error
          if (callbacks.onNotice) {
            callbacks.onNotice('Speech recognition network service unavailable in this browser. Please type commands directly.');
          } else {
            callbacks.onError({
              type: 'network',
              message: 'Speech recognition network service unavailable in this runtime. Try typed commands.',
            });
          }
        } else {
          callbacks.onError({
            type: 'unknown',
            message: `Speech recognition error: ${event.error || 'Unknown error'}`,
          });
        }
      };

      this.recognition.onend = () => {
        console.log('[VoiceService] SpeechRecognition session ended.');
        this.stopListening();
        callbacks.onEnd();
      };

      this.recognition.start();
    } catch (recErr: any) {
      console.warn('[VoiceService] Failed to start recognition:', recErr);
      callbacks.onError({
        type: 'unknown',
        message: recErr?.message || 'Could not start speech recognition session.',
      });
      this.stopListening();
      callbacks.onEnd();
      return false;
    }

    return true;
  }

  /**
   * Safely stops microphone recording and speech recognition,
   * releasing all audio tracks and AudioContext resources.
   */
  public stopListening(): void {
    this.isRecording = false;

    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }

    if (this.recognition) {
      try {
        this.recognition.onend = null;
        this.recognition.onerror = null;
        this.recognition.stop();
      } catch {
        // ignore
      }
      this.recognition = null;
    }

    if (this.activeStream) {
      try {
        this.activeStream.getTracks().forEach((track) => track.stop());
      } catch {
        // ignore
      }
      this.activeStream = null;
    }

    if (this.audioContext) {
      try {
        if (this.audioContext.state !== 'closed') {
          this.audioContext.close();
        }
      } catch {
        // ignore
      }
      this.audioContext = null;
      this.analyser = null;
    }
  }

  /**
   * Returns whether recording is currently active.
   */
  public getIsRecording(): boolean {
    return this.isRecording;
  }

  /**
   * Speaks a response text aloud using browser SpeechSynthesis if supported.
   */
  public speakResponse(text: string): void {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.1; // Friendly tone for Doraemon
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn('[VoiceService] Speech synthesis failed:', err);
    }
  }
}

export const voiceService = new VoiceService();

