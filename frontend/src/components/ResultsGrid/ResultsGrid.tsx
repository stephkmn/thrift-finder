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
}

const SKELETON_COUNT = 6;

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

const SOURCE_LABELS: Record<SearchResult['source'], string> = {
  ebay: 'eBay',
  local: 'Archive (not for sale)',
};

function ResultCard({ result }: { result: SearchResult }) {
  const score = Math.round(result.match_score);
  return (
    <li className={styles.item}>
      <article className={styles.card}>
        <img className={styles.image} src={result.image_url} alt={result.title} loading="lazy" />
        <div className={styles.body}>
          <span className={styles.source} data-source={result.source}>
            {SOURCE_LABELS[result.source]}
          </span>
          <h3 className={styles.title}>{result.title}</h3>
          <p className={styles.price} data-missing={result.price === null || undefined}>
            {result.price === null ? 'Price unavailable' : usd.format(result.price)}
          </p>
          <div className={styles.score}>
            <span className={styles.scoreLabel}>Match</span>
            <span className={styles.bar} aria-hidden="true">
              <span style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
            </span>
            <span className={styles.scoreNumber}>
              {score}
              <span className="visually-hidden"> out of 100</span>
            </span>
          </div>
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

/** Up to 10 ranked listings, plus loading, empty, and error states (S2-7). */
export function ResultsGrid({ state, onRetry }: ResultsGridProps) {
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
              <div className={`${styles.card} ${styles.skeleton}`}>
                <div className={styles.image} />
                <div className={styles.body}>
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
          No matches for these details yet. Try a different color or fabric, or remove a feature,
          then update your results.
        </p>
      )}

      {state.status === 'success' && count > 0 && (
        <ul className={styles.grid}>
          {state.results.map((result) => (
            <ResultCard key={result.id} result={result} />
          ))}
        </ul>
      )}
    </section>
  );
}
