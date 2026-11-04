import { useId, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import type { ExtractInput } from '../../api/client';
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
}

export function UploadForm({ onSubmit, disabled = false, intro, children }: UploadFormProps) {
  const [image, setImage] = useState<File | null>(null);
  const [text, setText] = useState('');
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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit({ image: image ?? undefined, text: trimmedText || undefined });
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
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
          Read the details
        </button>

        {children}
      </div>
    </form>
  );
}
