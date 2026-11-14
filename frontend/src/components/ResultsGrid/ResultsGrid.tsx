import { useId } from 'react';
import type { SearchResult } from '../../api/types';
import styles from './ResultsGrid.module.css';

export type ResultsState =
  | { status: 'loading' }
  | { status: 'success'; results: SearchResult[] }
  | { status: 'error'; message: string };

interface ResultsGridProps {
  state: ResultsState;
  /** Resends the same search after an error. */
  onRetry: () => void;
  /**
   * Opens the details page for a listing (S3-6). Without it, the photos are not clickable:
   * the details page doesn't exist yet, and a button that does nothing would be a trap.
   */
  onOpenDetails?: (id: string) => void;
}

const SKELETON_COUNT = 6;

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

const SOURCE_LABELS: Record<SearchResult['source'], string> = {
  ebay: 'eBay',
  local: 'Archive (not for sale)',
};

interface ResultCardProps {
  result: SearchResult;
  onOpenDetails?: (id: string) => void;
}

function ResultCard({ result, onOpenDetails }: ResultCardProps) {
  const titleId = useId();
  const score = Math.round(result.match_score);
  const image = (
    <img className={styles.image} src={result.image_url} alt={result.title} loading="lazy" />
  );
  return (
    <li className={styles.item}>
      <article className={styles.polaroid} aria-labelledby={titleId}>
        <div className={styles.photo}>
          {onOpenDetails ? (
            <button
              type="button"
              className={styles.photoButton}
              aria-label={`See details: ${result.title}`}
              data-listing-id={result.id}
              onClick={() => onOpenDetails(result.id)}
            >
              {image}
            </button>
          ) : (
            image
          )}
        </div>
        {/* Written on the frame: what you need to compare photos at a glance. The match score
            stays here in reading order (title, price, score) but is shown as a stamp on the photo. */}
        <div className={styles.caption}>
          <h3 id={titleId} className={styles.title}>
            {result.title}
          </h3>
          <p className={styles.meta}>
            <span className={styles.price} data-missing={result.price === null || undefined}>
              {result.price === null ? 'Price unavailable' : usd.format(result.price)}
            </span>
            <span className={styles.score}>
              <span className={styles.scoreLabel}>Match</span>
              <span className={styles.scoreNumber}>
                {score}
                <span className="visually-hidden"> out of 100</span>
              </span>
            </span>
          </p>
        </div>
        {/* With a mouse, these sit over the blurred photo on hover or keyboard focus.
            Touch screens have no hover, so there they stay under the caption. */}
        <div className={styles.details}>
          {onOpenDetails && (
            <span className={styles.hint} aria-hidden="true">
              See details
            </span>
          )}
          <span className={styles.source} data-source={result.source}>
            {SOURCE_LABELS[result.source]}
          </span>
          {result.listing_url && (
            <a
              className={styles.link}
              href={result.listing_url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`View listing: ${result.title} (opens in a new tab)`}
            >
              View listing
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="M6.5 3.5h-3v9h9v-3M9 3.5h3.5V7M12.5 3.5 7 9" />
              </svg>
            </a>
          )}
        </div>
      </article>
    </li>
  );
}

/**
 * Up to 10 ranked listings as a polaroid board (S3-5), plus loading, empty, and error states (S2-7).
 */
export function ResultsGrid({ state, onRetry, onOpenDetails }: ResultsGridProps) {
  const titleId = useId();
  const count = state.status === 'success' ? state.results.length : 0;

  return (
    <section
      className={styles.results}
      aria-labelledby={titleId}
      aria-busy={state.status === 'loading'}
    >
      <h2 id={titleId} className={styles.heading}>
        Top matches
      </h2>

      <p className={styles.status} aria-live="polite">
        {state.status === 'loading' && 'Finding matches…'}
        {state.status === 'success' &&
          count > 0 &&
          `${count} ${count === 1 ? 'match' : 'matches'}, best first.`}
      </p>

      {state.status === 'loading' && (
        <ul className={styles.grid} aria-hidden="true" data-testid="results-skeleton">
          {Array.from({ length: SKELETON_COUNT }, (_, i) => (
            <li key={i} className={styles.item}>
              <div className={`${styles.polaroid} ${styles.skeleton}`}>
                <div className={styles.photo} />
                <div className={styles.caption}>
                  <span className={styles.line} />
                  <span className={styles.line} data-short />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {state.status === 'error' && (
        <div className={styles.error} role="alert">
          <p className={styles.errorMessage}>
            <svg
              className={styles.errorIcon}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7.5v5.5" />
              <path d="M12 16.5h.01" />
            </svg>
            {state.message}
          </p>
          <button type="button" className={styles.retry} onClick={onRetry}>
            Retry
          </button>
        </div>
      )}

      {state.status === 'success' && count === 0 && (
        <p className={styles.empty}>
          No matches for these details. Try a different color or fabric, or remove a feature, then
          update your results.
        </p>
      )}

      {state.status === 'success' && count > 0 && (
        <ul className={styles.grid}>
          {state.results.map((result) => (
            <ResultCard key={result.id} result={result} onOpenDetails={onOpenDetails} />
          ))}
        </ul>
      )}
    </section>
  );
}
