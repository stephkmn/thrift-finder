import { useId } from 'react';
import type { Ref } from 'react';
import type { ExtractInput } from '../../api/client';
import { useObjectUrl } from '../../lib/useObjectUrl';
import styles from './UploadSummary.module.css';

interface UploadSummaryProps {
  input: ExtractInput;
  queryId: string;
  onEdit: () => void;
  onStartOver: () => void;
  /** Receives focus when the form collapses, so keyboard users are not dropped on <body>. */
  headingRef?: Ref<HTMLHeadingElement>;
}

/** The collapsed upload form: what the user gave us, with ways back. */
export function UploadSummary({
  input,
  queryId,
  onEdit,
  onStartOver,
  headingRef,
}: UploadSummaryProps) {
  const titleId = useId();
  // Revoked when the summary unmounts (Edit upload, Start over).
  const photoUrl = useObjectUrl(input.image);

  return (
    <section className={styles.summary} aria-labelledby={titleId}>
      {input.image && (
        <div className={styles.thumb}>{photoUrl && <img src={photoUrl} alt="Your photo" />}</div>
      )}
      <div className={styles.details}>
        <h2 id={titleId} ref={headingRef} tabIndex={-1} className={styles.title}>
          Your upload
        </h2>
        {input.text ? (
          <p className={styles.text}>&ldquo;{input.text}&rdquo;</p>
        ) : (
          <p className={styles.muted}>Photo only, no description</p>
        )}
        <p className={styles.queryId}>
          Query ID: <code>{queryId}</code>
        </p>
      </div>
      <div className={styles.actions}>
        <button type="button" className={styles.button} onClick={onEdit}>
          Edit upload
        </button>
        <button type="button" className={styles.button} onClick={onStartOver}>
          Start over
        </button>
      </div>
    </section>
  );
}
