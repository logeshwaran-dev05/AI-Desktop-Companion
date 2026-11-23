/**
 * Voice Interaction Service
 * =========================
 * Manages microphone audio stream, live audio volume metering (via Web Audio API
 * AnalyserNode), speech-to-text recognition (via Web Speech API SpeechRecognition),
 * and spoken voice output (via SpeechSynthesis).
 *
 * Capabilities:
 * - Real-time microphone audio metering (0-100% scale) for waveforms & diagnostic tests
 * - Resilient speech-to-text with full transcript aggregation across interim & final events
 * - Graceful fallback and notice when cloud speech services are offline or blocked
 * - Built-in Voice Testing Suite: mic hardware test, TTS speaker test, voice simulation
 * - Safe resource cleanup preventing device locks and memory leaks
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
  onError?: (error: VoiceError) => void;
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
  private simulationTimer: ReturnType<typeof setTimeout> | null = null;

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
      throw new Error('Microphone access is not supported on this platform.');
    }
    return await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });
  }

  /**
   * Starts a voice recording session.
   * Connects microphone audio to Web Audio AnalyserNode for live waveform visualizer,
   * and initializes SpeechRecognition if supported.
   */
  public async startListening(callbacks: VoiceSessionCallbacks): Promise<boolean> {
    // Prevent duplicate recording sessions
    if (this.isRecording) {
      this.stopListening();
    }

    this.isRecording = true;

    // 1. Attempt live audio metering for waveform animation (non-blocking)
    try {
      this.activeStream = await this.requestMicrophoneAccess();
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx && this.activeStream) {
        this.audioContext = new AudioCtx();
        if (this.audioContext.state === 'suspended') {
          await this.audioContext.resume().catch(() => {});
        }
        const source = this.audioContext.createMediaStreamSource(this.activeStream);
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 64;
        this.analyser.smoothingTimeConstant = 0.5;
        source.connect(this.analyser);

        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        const pollAudioLevel = () => {
          if (!this.isRecording || !this.analyser) return;
          this.analyser.getByteFrequencyData(dataArray);

          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const average = sum / dataArray.length;
          const normalized = Math.min(100, Math.round((average / 128) * 100));

          if (callbacks.onAudioLevel) {
            callbacks.onAudioLevel(normalized);
          }

          this.animFrameId = requestAnimationFrame(pollAudioLevel);
        };

        this.animFrameId = requestAnimationFrame(pollAudioLevel);
      }
    } catch (meterErr: unknown) {
      console.warn('[VoiceService] AudioContext metering init skipped or mic busy:', meterErr);
      // Metering failure must not block speech recognition attempt
    }

    // 2. Electron runtime: Chromium's Web Speech API is blocked by Google (missing API keys).
    // Automatically trigger native Windows Voice Typing in the background and keep the microphone
    // recording session active with live volume waveforms and direct dictate-to-input automation.
    const isElectronEnv = typeof window !== 'undefined' && Boolean((window as any).companionAPI?.isElectron);
    if (isElectronEnv) {
      console.log('[VoiceService] Electron runtime: engaging automatic background Voice Typing & mic metering...');
      if (window.companionAPI?.triggerVoiceTyping) {
        window.companionAPI.triggerVoiceTyping().catch((err: any) => {
          console.warn('[VoiceService] triggerVoiceTyping warning:', err);
        });
      }
      if (callbacks.onNotice) {
        callbacks.onNotice('🎤 Microphone active. Speak your command (e.g. "Open Notepad" or "Open Calculator").');
      }
      return true;
    }

    // 3. Browser runtime (Chrome/Edge): Use built-in SpeechRecognition
    if (!this.isRecognitionSupported()) {
      if (callbacks.onNotice) {
        callbacks.onNotice('Speech recognition engine not built-in. Type your command or click a quick test chip.');
      }
      if (callbacks.onError) {
        callbacks.onError({
          type: 'unsupported',
          message: 'Speech recognition engine is not supported in this runtime. Type commands or click a quick test chip.',
        });
      }
      return true;
    }

    try {
      const win = window as IWindowSpeech;
      const SpeechRecognitionConstructor = win.SpeechRecognition || win.webkitSpeechRecognition;
      this.recognition = new SpeechRecognitionConstructor();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.maxAlternatives = 1;
      this.recognition.lang = 'en-US';

      this.recognition.onstart = () => {
        console.log('[VoiceService] SpeechRecognition session started.');
      };

      this.recognition.onresult = (event: any) => {
        let finalTranscript = '';
        let interimTranscript = '';

        // Iterate through all results to build full continuous speech
        for (let i = 0; i < event.results.length; ++i) {
          const result = event.results[i];
          if (result && result[0]) {
            if (result.isFinal) {
              finalTranscript += result[0].transcript + ' ';
            } else {
              interimTranscript += result[0].transcript;
            }
          }
        }

        const fullText = (finalTranscript + interimTranscript).trim();
        if (fullText) {
          callbacks.onTranscript(fullText, Boolean(finalTranscript.trim() && !interimTranscript.trim()));
        }
      };

      this.recognition.onerror = (event: any) => {
        console.warn('[VoiceService] SpeechRecognition error:', event.error);
        if (event.error === 'no-speech') {
          // Expected when user pauses; do not abort recording session immediately
          return;
        }

        if (event.error === 'network') {
          console.warn('[VoiceService] Web speech network unreachable (offline or blocked).');
          if (callbacks.onNotice) {
            callbacks.onNotice('Speech service unreachable. Type your command or click a quick test chip.');
          }
          return;
        }

        if (event.error === 'not-allowed') {
          if (callbacks.onError) {
            callbacks.onError({
              type: 'not-allowed',
              message: 'Microphone permission denied by system. Please check Windows Privacy & security settings.',
            });
          }
          this.stopListening();
          callbacks.onEnd();
          return;
        }

        if (event.error === 'audio-capture') {
          if (callbacks.onError) {
            callbacks.onError({
              type: 'audio-capture',
              message: 'No microphone was detected or audio device is busy.',
            });
          }
          this.stopListening();
          callbacks.onEnd();
          return;
        }

        if (callbacks.onError) {
          callbacks.onError({
            type: 'unknown',
            message: `Speech recognition notice: ${event.error || 'Check microphone connection'}`,
          });
        }
      };

      this.recognition.onend = () => {
        console.log('[VoiceService] SpeechRecognition session ended.');
        if (this.isRecording && !isElectronEnv) {
          // If ended unexpectedly while still in recording mode, finalize session
          this.stopListening();
          callbacks.onEnd();
        }
      };

      this.recognition.start();
    } catch (recErr: any) {
      console.warn('[VoiceService] Failed to start recognition instance:', recErr);
      if (callbacks.onNotice) {
        callbacks.onNotice('Microphone active. Speak into the prompt or click a test command.');
      }
    }

    return true;
  }

  /**
   * Dedicated microphone hardware test:
   * Opens microphone audio stream and provides continuous audio level updates (0-100%).
   * Returns a cleanup function to stop the test.
   */
  public async testMicrophone(onAudioLevel: (level: number) => void): Promise<() => void> {
    const stream = await this.requestMicrophoneAccess();
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioCtx) {
      throw new Error('Web Audio API is not supported on this platform.');
    }

    const ctx = new AudioCtx();
    if (ctx.state === 'suspended') {
      await ctx.resume().catch(() => {});
    }

    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 64;
    source.connect(analyser);

    let active = true;
    let frameId: number | null = null;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const checkLevel = () => {
      if (!active) return;
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const avg = sum / dataArray.length;
      const normalized = Math.min(100, Math.round((avg / 128) * 100));
      onAudioLevel(normalized);
      frameId = requestAnimationFrame(checkLevel);
    };

    frameId = requestAnimationFrame(checkLevel);

    return () => {
      active = false;
      if (frameId !== null) cancelAnimationFrame(frameId);
      try {
        stream.getTracks().forEach((t) => t.stop());
        if (ctx.state !== 'closed') ctx.close().catch(() => {});
      } catch {
        // ignore
      }
      onAudioLevel(0);
    };
  }

  /**
   * Simulates a voice command for testing and offline environments.
   * Generates simulated live audio meter waveforms, word-by-word streaming transcripts,
   * and dispatches final command to callbacks.
   */
  public async simulateVoiceCommand(
    command: string,
    callbacks: VoiceSessionCallbacks
  ): Promise<void> {
    this.stopListening();
    this.isRecording = true;

    // Simulate animated waveform audio levels
    let step = 0;
    const waveInterval = setInterval(() => {
      if (!this.isRecording) {
        clearInterval(waveInterval);
        return;
      }
      step++;
      const simulatedLevel = Math.round(35 + Math.sin(step * 0.7) * 35 + (step % 3) * 10);
      if (callbacks.onAudioLevel) {
        callbacks.onAudioLevel(Math.min(95, Math.max(15, simulatedLevel)));
      }
    }, 70);

    const words = command.trim().split(/\s+/);
    let cumulative = '';

    for (let i = 0; i < words.length; i++) {
      if (!this.isRecording) {
        clearInterval(waveInterval);
        return;
      }
      cumulative = (cumulative + ' ' + words[i]).trim();
      const isFinal = i === words.length - 1;
      callbacks.onTranscript(cumulative, isFinal);
      await new Promise((r) => setTimeout(r, 220));
    }

    // Brief pause before finalizing
    await new Promise((r) => setTimeout(r, 300));
    clearInterval(waveInterval);

    this.isRecording = false;
    if (callbacks.onAudioLevel) {
      callbacks.onAudioLevel(0);
    }
    callbacks.onEnd();
  }

  /**
   * Safely stops microphone recording and speech recognition,
   * releasing all audio tracks and AudioContext resources.
   */
  public stopListening(): void {
    this.isRecording = false;

    if (this.simulationTimer !== null) {
      clearTimeout(this.simulationTimer);
      this.simulationTimer = null;
    }

    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }

    if (this.recognition) {
      try {
        this.recognition.onend = null;
        this.recognition.onerror = null;
        this.recognition.onresult = null;
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
  public speakResponse(text: string, onEnd?: () => void): void {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      // Clean emojis and symbols for speech synthesis
      const cleanText = text.replace(/[\u{1F300}-\u{1FAFF}]/gu, '').replace(/[✦⧗✔✖⏹⚠⊘◈◷⚙]/g, '').trim();
      if (!cleanText) return;

      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.rate = 1.05;
      utterance.pitch = 1.1; // Friendly Doraemon pitch

      if (onEnd) {
        utterance.onend = onEnd;
        utterance.onerror = () => onEnd();
      }

      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn('[VoiceService] Speech synthesis failed:', err);
      if (onEnd) onEnd();
    }
  }
}

export const voiceService = new VoiceService();
