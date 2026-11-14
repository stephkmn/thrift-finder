import { useEffect, useRef } from 'react';
import type { Attributes, SearchResult } from '../api/types';
import styles from './DetailsPage.module.css';

interface DetailsPageProps {
  /** The listing id from the URL. */
  id: string;
  /** The listing as the board showed it, when it came from the current results. */
  result?: SearchResult;
  /** `edited_attributes` of the search that produced the board, for the comparison. */
  searched: Attributes | null;
  onBack: () => void;
}

/** One listing, opened from a polaroid (S3-6). */
export function DetailsPage({ id, result, onBack }: DetailsPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  // A new page: start at the top, with focus on its heading for keyboard and screen readers.
  useEffect(() => {
    window.scrollTo({ top: 0 });
    headingRef.current?.focus();
  }, []);

  return (
    <article className={styles.details} aria-labelledby="details-title">
      <button type="button" className={styles.back} onClick={onBack}>
        Back to results
      </button>
      <h2 id="details-title" ref={headingRef} tabIndex={-1} className={styles.title}>
        {result?.title ?? id}
      </h2>
    </article>
  );
}
