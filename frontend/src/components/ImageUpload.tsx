import React, { useState, useRef } from "react";
import { Image as ImageIcon, X, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { compressImage, CompressionResult } from "../utils/imageCompress";
import { apiBaseUrl, apiMultipartHeaders } from "../config";

interface ImageUploadProps {
  onImageExtracted: (findings: any[], previewUrl: string) => void;
  onClear: () => void;
  disabled?: boolean;
}

export const ImageUpload: React.FC<ImageUploadProps> = ({
  onImageExtracted,
  onClear,
  disabled,
}) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [fileStats, setFileStats] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);
    setErrorMessage(null);
    setStatusMessage("Compressing image...");

    try {
      // 1. Client-side canvas compression (max 1024px, JPEG 0.6)
      const compressed: CompressionResult = await compressImage(file, 1024, 0.6);
      setPreviewUrl(compressed.dataUrl);
      const originalKb = (compressed.originalSize / 1024).toFixed(0);
      const compressedKb = (compressed.compressedSize / 1024).toFixed(0);
      setFileStats(`${compressedKb} KB (from ${originalKb} KB)`);

      setStatusMessage("Extracting visual evidence with Gemini Vision...");

      // 2. Upload to POST /api/image
      const formData = new FormData();
      formData.append("file", compressed.blob, "upload.jpg");

      const response = await fetch(`${apiBaseUrl}/api/image`, {
        method: "POST",
        headers: apiMultipartHeaders(),
        body: formData,
      });

      if (!response.ok) {
        const errPayload = await response.json().catch(() => null);
        throw new Error(errPayload?.detail || "Image analysis failed");
      }

      const data = await response.json();
      const findings = data.findings || [];
      setStatusMessage(`Extracted ${findings.length} visual findings`);
      onImageExtracted(findings, compressed.dataUrl);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to analyze image");
      setPreviewUrl(null);
      setFileStats(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRemove = () => {
    setPreviewUrl(null);
    setFileStats(null);
    setStatusMessage(null);
    setErrorMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    onClear();
  };

  return (
    <div className="flex flex-col gap-2">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/png,image/jpeg,image/webp,image/jpg"
        className="hidden"
        disabled={disabled || isProcessing}
      />

      {!previewUrl && (
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || isProcessing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-700/70 bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          title="Attach image or chart for visual evidence extraction"
        >
          <ImageIcon className="w-3.5 h-3.5 text-violet-400" />
          <span>Attach Image / Chart</span>
        </button>
      )}

      {previewUrl && (
        <div className="flex items-center justify-between gap-3 p-2.5 rounded-2xl bg-slate-900 border border-slate-800">
          <div className="flex items-center gap-3">
            <img
              src={previewUrl}
              alt="Attached preview"
              className="h-10 w-10 rounded-lg object-cover border border-slate-700"
            />
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5 text-xs font-medium text-slate-200">
                {isProcessing ? (
                  <Loader2 className="w-3 h-3 animate-spin text-indigo-400" />
                ) : (
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                )}
                <span>{statusMessage || "Image attached"}</span>
              </div>
              {fileStats && <span className="text-[11px] text-slate-400">{fileStats}</span>}
            </div>
          </div>

          <button
            type="button"
            onClick={handleRemove}
            disabled={isProcessing}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-rose-400 transition-colors"
            title="Remove image"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
