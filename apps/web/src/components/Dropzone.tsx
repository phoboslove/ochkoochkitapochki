"use client";

import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

export function Dropzone({ onFiles, accept = ".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.tiff,.webp" }: {
  onFiles: (files: File[]) => void;
  accept?: string;
}) {
  const [over, setOver] = useState(false);
  const ref = useRef<HTMLInputElement>(null);

  const handle = useCallback((files: FileList | null) => {
    if (!files?.length) return;
    onFiles(Array.from(files));
  }, [onFiles]);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); handle(e.dataTransfer.files); }}
      onClick={() => ref.current?.click()}
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 cursor-pointer transition-colors",
        over ? "border-primary bg-accent/40" : "border-border hover:bg-accent/20",
      )}
    >
      <Upload className="h-5 w-5 text-muted-foreground" />
      <div className="text-sm font-medium">Drop files here or click to upload</div>
      <div className="text-xs text-muted-foreground">PDF, DOCX, XLSX, images · up to 25 MB</div>
      <input ref={ref} type="file" multiple accept={accept} className="hidden"
             onChange={(e) => handle(e.target.files)} />
    </div>
  );
}
