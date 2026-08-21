/**
 * Client-side image compression using HTML Canvas.
 * Resizes images to max 1024px while preserving aspect ratio,
 * and encodes to JPEG with 0.6 quality to ensure payload is under 500KB.
 */

export interface CompressionResult {
  blob: Blob;
  dataUrl: string;
  originalSize: number;
  compressedSize: number;
  mimeType: string;
}

export async function compressImage(
  file: File,
  maxDimension = 1024,
  quality = 0.6
): Promise<CompressionResult> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const reader = new FileReader();

    reader.onload = (e) => {
      if (!e.target?.result) {
        reject(new Error("Failed to read image file"));
        return;
      }
      img.src = e.target.result as string;
    };

    reader.onerror = () => reject(new Error("Error reading image file"));

    img.onload = () => {
      let { width, height } = img;

      // Scale down proportionally if larger than maxDimension
      if (width > maxDimension || height > maxDimension) {
        if (width > height) {
          height = Math.round((height * maxDimension) / width);
          width = maxDimension;
        } else {
          width = Math.round((width * maxDimension) / height);
          height = maxDimension;
        }
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("Failed to get 2D canvas context"));
        return;
      }

      // Draw white background for transparent PNGs converted to JPEG
      ctx.fillStyle = "#FFFFFF";
      ctx.fillRect(0, 0, width, height);
      ctx.drawImage(img, 0, 0, width, height);

      const mimeType = "image/jpeg";
      const dataUrl = canvas.toDataURL(mimeType, quality);

      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error("Canvas blob conversion failed"));
            return;
          }
          resolve({
            blob,
            dataUrl,
            originalSize: file.size,
            compressedSize: blob.size,
            mimeType,
          });
        },
        mimeType,
        quality
      );
    };

    img.onerror = () => reject(new Error("Failed to load image"));
    reader.readAsDataURL(file);
  });
}
