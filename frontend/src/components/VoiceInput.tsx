import React, { useState, useRef, useEffect } from "react";
import { Mic, Square, Loader2, Volume2, AlertCircle } from "lucide-react";
import { apiBaseUrl, apiHeaders } from "../config";

interface VoiceInputProps {
  onTranscribed: (text: string) => void;
  disabled?: boolean;
}

export const VoiceInput: React.FC<VoiceInputProps> = ({ onTranscribed, disabled }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [cooldownActive, setCooldownActive] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const cooldownTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      if (cooldownTimerRef.current) window.clearTimeout(cooldownTimerRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const startRecording = async () => {
    setErrorMessage(null);
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/ogg";

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all tracks to release mic
        stream.getTracks().forEach((track) => track.stop());

        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        if (audioBlob.size > 0) {
          await uploadAndTranscribe(audioBlob);
        }
      };

      mediaRecorder.start(250); // Slice every 250ms
      setIsRecording(true);
      setRecordingTime(0);

      timerRef.current = window.setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      setErrorMessage(
        err instanceof Error && err.name === "NotAllowedError"
          ? "Microphone permission denied. Please allow microphone access."
          : "Unable to access microphone."
      );
    }
  };

  const stopRecording = () => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const uploadAndTranscribe = async (audioBlob: Blob) => {
    setIsTranscribing(true);
    setErrorMessage(null);

    const formData = new FormData();
    formData.append("file", audioBlob, "recording.webm");

    try {
      const response = await fetch(`${apiBaseUrl}/api/voice`, {
        method: "POST",
        headers: apiHeaders(),
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || "Voice transcription failed");
      }

      const data = (await response.json()) as { text: string };
      if (data.text && data.text.trim()) {
        onTranscribed(data.text.trim());
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Transcription failed");
    } finally {
      setIsTranscribing(false);
      setCooldownActive(true);
      if (cooldownTimerRef.current) window.clearTimeout(cooldownTimerRef.current);
      cooldownTimerRef.current = window.setTimeout(() => {
        setCooldownActive(false);
        cooldownTimerRef.current = null;
      }, 2500);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        {!isRecording && !isTranscribing && !cooldownActive && (
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-700/70 bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            title="Voice query input via Groq Whisper"
          >
            <Mic className="w-3.5 h-3.5 text-indigo-400" />
            <span>Voice Input</span>
          </button>
        )}

        {cooldownActive && !isRecording && !isTranscribing && (
          <button
            type="button"
            disabled
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-700/50 bg-slate-800/50 text-slate-400 text-xs font-medium opacity-60 cursor-not-allowed"
            title="Cooldown active"
          >
            <Mic className="w-3.5 h-3.5 text-slate-500" />
            <span>Cooling down...</span>
          </button>
        )}

        {isRecording && (
          <div className="flex items-center gap-3 px-3.5 py-1.5 rounded-xl bg-rose-500/10 border border-rose-500/40 text-rose-300 text-xs font-medium animate-pulse">
            <span className="flex h-2 w-2 rounded-full bg-rose-500 animate-ping" />
            <Volume2 className="w-3.5 h-3.5 text-rose-400" />
            <span>Recording ({formatTime(recordingTime)})</span>
            <button
              type="button"
              onClick={stopRecording}
              className="ml-2 flex items-center gap-1 px-2 py-0.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition-all"
            >
              <Square className="w-3 h-3 fill-current" />
              <span>Done</span>
            </button>
          </div>
        )}

        {isTranscribing && (
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-medium">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
            <span>Transcribing with Whisper...</span>
          </div>
        )}
      </div>

      {errorMessage && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
