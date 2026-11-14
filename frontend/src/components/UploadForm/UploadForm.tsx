import { useEffect, useEffectEvent, useId, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import type { ExtractInput } from '../../api/client';
import { imageFromClipboard } from '../../lib/clipboardImage';
import { validateImage } from '../../lib/validateImage';
import { DropZone } from '../DropZone/DropZone';
import styles from './UploadForm.module.css';

interface UploadFormProps {
  onSubmit: (input: ExtractInput) => void;
  /** True while a request is in flight. */
  disabled?: boolean;
  /** Heading content; sits above the details column on wide screens. */
  intro?: ReactNode;
  /** Request status and results, rendered below the submit button. */
  children?: ReactNode;
  /** Pre-fills the form, e.g. when the user goes back to edit their upload. */
  initialInput?: ExtractInput;
}

export function UploadForm({
  onSubmit,
  disabled = false,
  intro,
  children,
  initialInput,
}: UploadFormProps) {
  const [image, setImage] = useState<File | null>(initialInput?.image ?? null);
  const [text, setText] = useState(initialInput?.text ?? '');
  const [fileError, setFileError] = useState<string | null>(null);
  const textId = useId();
  const fileErrorId = useId();

  const trimmedText = text.trim();
  const canSubmit = !disabled && (image !== null || trimmedText !== '');

  const handleFileChosen = (file: File) => {
    const problem = validateImage(file);
    setFileError(problem);
    if (!problem) setImage(file);
  };

  // Paste a copied image or screenshot anywhere on the page (or into the description box on a
  // phone). Pasted text still goes into the description as usual.
  const formRef = useRef<HTMLFormElement>(null);
  const handlePaste = useEffectEvent((event: ClipboardEvent) => {
    // The form stays mounted but hidden while a details page is open; don't change it then.
    if (!formRef.current || formRef.current.closest('[hidden]')) return;
    const image = imageFromClipboard(event.clipboardData);
    if (!image) return;
    event.preventDefault();
    handleFileChosen(image);
  });
  useEffect(() => {
    if (disabled) return;
    const listener = (event: ClipboardEvent) => handlePaste(event);
    document.addEventListener('paste', listener);
    return () => document.removeEventListener('paste', listener);
  }, [disabled]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit({ image: image ?? undefined, text: trimmedText || undefined });
  };

  return (
    <form ref={formRef} className={styles.form} onSubmit={handleSubmit} noValidate>
      {intro && <div className={styles.intro}>{intro}</div>}

      <fieldset className={styles.photo} disabled={disabled}>
        <legend className="visually-hidden">Photo</legend>
        <DropZone
          file={image}
          onFileChosen={handleFileChosen}
          onRemove={() => {
            setImage(null);
            setFileError(null);
          }}
          disabled={disabled}
          errorId={fileError ? fileErrorId : undefined}
        />
        {fileError && (
          <p id={fileErrorId} className={styles.fieldError} role="alert">
            {fileError}
          </p>
        )}
      </fieldset>

      <div className={styles.details}>
        <div className={styles.field}>
          <label htmlFor={textId} className={styles.label}>
            Description <span className={styles.optional}>(optional)</span>
          </label>
          <textarea
            id={textId}
            className={styles.textarea}
            rows={3}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Describe it, e.g. 'brown suede jacket with a hood'"
            disabled={disabled}
          />
        </div>

        <button type="submit" className={styles.submit} disabled={!canSubmit}>
          Find its details
        </button>

        {children}
      </div>
    </form>
  );
}
