import { useEffect, useId, useRef, useState } from 'react';
import type { DragEvent, KeyboardEvent } from 'react';
import { ACCEPTED_IMAGE_TYPES } from '../../lib/validateImage';
import styles from './DropZone.module.css';

interface DropZoneProps {
  file: File | null;
  /** Called with whatever the user picked or dropped; the parent validates it. */
  onFileChosen: (file: File) => void;
  onRemove: () => void;
  disabled?: boolean;
  /** id of an element describing the current problem, e.g. a validation error. */
  errorId?: string;
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DropZone({ file, onFileChosen, onRemove, disabled, errorId }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const hintId = useId();
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // The preview URL is the only reference to the image outside React state; revoke it
  // on replace, remove, and unmount so the photo never outlives the page in memory.
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing with an external resource
    setPreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
      setPreviewUrl(null);
    };
  }, [file]);

  const openPicker = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openPicker();
    }
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setIsDragging(false);
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped && !disabled) onFileChosen(dropped);
  };

  const dragProps = {
    onDragOver: handleDragOver,
    onDragEnter: handleDragOver,
    onDragLeave: handleDragLeave,
    onDrop: handleDrop,
  };

  return (
    <div className={styles.root}>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept={ACCEPTED_IMAGE_TYPES.join(',')}
        aria-label="Photo file"
        tabIndex={-1}
        disabled={disabled}
        onChange={(event) => {
          const picked = event.target.files?.[0];
          // Reset so choosing the same file again after removing it still fires onChange.
          event.target.value = '';
          if (picked) onFileChosen(picked);
        }}
      />

      {file ? (
        <div className={styles.selected} data-dragging={isDragging || undefined} {...dragProps}>
          <div className={styles.thumb}>
            {previewUrl && <img src={previewUrl} alt="Preview of the selected photo" />}
          </div>
          <div className={styles.meta}>
            <p className={styles.fileName} title={file.name}>
              {file.name}
            </p>
            <p className={styles.fileSize}>{formatSize(file.size)}</p>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.textButton}
                onClick={openPicker}
                disabled={disabled}
              >
                Replace
              </button>
              <button
                type="button"
                className={styles.textButton}
                onClick={onRemove}
                disabled={disabled}
              >
                Remove
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div
          className={styles.zone}
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-disabled={disabled || undefined}
          aria-label="Add a photo"
          aria-describedby={[hintId, errorId].filter(Boolean).join(' ')}
          data-dragging={isDragging || undefined}
          onClick={openPicker}
          onKeyDown={handleKeyDown}
          {...dragProps}
        >
          <svg
            className={styles.icon}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <circle cx="9" cy="10" r="1.75" />
            <path d="m21 16-4.5-4.5L8 20" />
          </svg>
          <p className={styles.prompt}>
            {isDragging ? 'Drop to add this photo' : 'Drop a photo here or browse'}
          </p>
          <p id={hintId} className={styles.hint}>
            JPG, PNG, or WebP, up to 10 MB
          </p>
        </div>
      )}
    </div>
  );
}
