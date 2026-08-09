import { Upload, X } from "lucide-react";
import { useCallback, useState } from "react";
import { cn } from "../../utils/helpers";

interface FileUploadProps {
  readonly label?: string;
  readonly description?: string;
  readonly error?: string;
  readonly accept?: string;
  readonly multiple?: boolean;
  readonly maxFiles?: number;
  readonly maxSizeMB?: number;
  readonly onChange?: (files: File[]) => void;
  readonly disabled?: boolean;
}

export function FileUpload({
  label,
  description,
  error,
  accept,
  multiple = false,
  maxFiles = 5,
  maxSizeMB = 10,
  onChange,
  disabled,
}: FileUploadProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);

  const validate = useCallback(
    (incoming: File[]): File[] => {
      const valid: File[] = [];
      for (const f of incoming) {
        const sizeMB = f.size / (1024 * 1024);
        if (sizeMB > maxSizeMB) continue;
        if (files.length + valid.length >= maxFiles) break;
        valid.push(f);
      }
      return valid;
    },
    [files.length, maxFiles, maxSizeMB],
  );

  const handleFiles = useCallback(
    (incoming: FileList | null) => {
      if (!incoming) return;
      const arr = Array.from(incoming);
      const valid = validate(arr);
      const next = [...files, ...valid];
      setFiles(next);
      onChange?.(next);
    },
    [files, validate, onChange],
  );

  const removeFile = useCallback(
    (index: number) => {
      const next = files.filter((_, i) => i !== index);
      setFiles(next);
      onChange?.(next);
    },
    [files, onChange],
  );

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor="file-upload-input"
          className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
        >
          {label}
        </label>
      )}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={cn(
          "relative rounded-lg border-2 border-dashed p-6 text-center transition-all duration-150",
          dragOver
            ? "border-[var(--color-brand-500)] bg-[var(--color-brand-500)]/5"
            : "border-[var(--border-primary)] hover:border-[var(--color-brand-500)]/50",
          disabled && "opacity-50 cursor-not-allowed",
        )}
      >
        <input
          id="file-upload-input"
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={disabled}
          onChange={(e) => handleFiles(e.target.files)}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
        />
        <Upload className="w-8 h-8 mx-auto text-[var(--text-muted)] mb-2" />
        <p className="text-sm text-[var(--text-secondary)]">
          Drop files here or <span className="text-[var(--color-brand-500)] underline">browse</span>
        </p>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          {multiple ? `Up to ${maxFiles} files, ${maxSizeMB}MB each` : `Max ${maxSizeMB}MB`}
        </p>
      </div>
      {files.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {files.map((f, i) => (
            <li
              key={`${f.name}-${i}`}
              className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-primary)]"
            >
              <span className="text-xs text-[var(--text-secondary)] truncate max-w-[200px]">
                {f.name}
              </span>
              <span className="text-[10px] text-[var(--text-muted)] mr-2">
                {(f.size / 1024).toFixed(1)}KB
              </span>
              <button
                type="button"
                onClick={() => removeFile(i)}
                className="text-[var(--text-muted)] hover:text-[var(--color-danger)] transition-colors"
                tabIndex={-1}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {description && !error && (
        <p className="mt-1 text-xs text-[var(--text-muted)]">{description}</p>
      )}
      {error && <p className="mt-1 text-xs text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}
