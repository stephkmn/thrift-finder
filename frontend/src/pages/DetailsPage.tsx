import { useEffect, useId, useRef, useState } from 'react';
import { ApiError, getItem } from '../api/client';
import type { AttributeComparison, Attributes, ItemDetails, SearchResult } from '../api/types';
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

type ItemState =
  | { status: 'loading' }
  | { status: 'success'; item: ItemDetails }
  | { status: 'error'; notFound: boolean; message: string };

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

const ATTRIBUTE_LABELS: Record<AttributeComparison['attribute'], string> = {
  category: 'Category',
  color: 'Color',
  fabric: 'Fabric',
  fit: 'Fit',
};

const DATASET_LABELS = [
  ['type', 'Type'],
  ['category', 'Category'],
  ['colors', 'Colors'],
  ['material', 'Material'],
  ['cut', 'Cut'],
  ['pattern', 'Pattern'],
  ['brand', 'Brand'],
] as const;

const FALLBACK_ERROR = 'This listing could not be loaded. Please try again.';

function Verdict({ match }: { match: boolean | null }) {
  if (match === null) return <span className={styles.unknown}>Not labeled</span>;
  return (
    <span className={match ? styles.match : styles.mismatch}>
      <span aria-hidden="true">{match ? '✓' : '✗'}</span> {match ? 'Matches' : 'Different'}
    </span>
  );
}

/** Your searched attributes next to the listing's dataset labels. */
function WhyItMatched({ item, searched }: { item: ItemDetails; searched: Attributes | null }) {
  const headingId = useId();
  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h3 id={headingId} className={styles.sectionTitle}>
        Why it matched
      </h3>
      {item.comparison.length === 0 ? (
        <p className={styles.note}>
          {searched
            ? 'This listing has no labels to compare.'
            : 'Search again to compare this listing with your attributes.'}
        </p>
      ) : (
        <>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Attribute</th>
                <th scope="col">You searched</th>
                <th scope="col">This listing</th>
                <th scope="col">
                  <span className="visually-hidden">Result</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {item.comparison.map((row) => (
                <tr key={row.attribute}>
                  <th scope="row">{ATTRIBUTE_LABELS[row.attribute]}</th>
                  <td>{row.yours}</td>
                  <td>{row.listing ?? '—'}</td>
                  <td>
                    <Verdict match={row.match} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className={styles.note}>
            Labels come from the dataset. The match score also accounts for visual similarity
            between the photos, so a listing can rank highly even when a label differs.
          </p>
        </>
      )}
    </section>
  );
}

function DatasetFacts({ item }: { item: ItemDetails }) {
  const headingId = useId();
  const facts = DATASET_LABELS.flatMap(([key, label]) => {
    const value = item.dataset_labels[key];
    const text = Array.isArray(value) ? value.join(', ') : value;
    return text ? [{ label, text }] : [];
  });
  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h3 id={headingId} className={styles.sectionTitle}>
        From the dataset
      </h3>
      {facts.length > 0 && (
        <dl className={styles.facts}>
          {facts.map(({ label, text }) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{text}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className={styles.credit}>
        Photo and labels:{' '}
        <a href={item.credit.url} target="_blank" rel="noopener noreferrer">
          {item.credit.text}
          <span className="visually-hidden"> (opens in a new tab)</span>
        </a>
      </p>
    </section>
  );
}

/** One listing, opened from a polaroid (S3-6). */
export function DetailsPage({ id, result, searched, onBack }: DetailsPageProps) {
  const titleId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  // eBay listings are never stored, so their details come only from the search result.
  const isEbay = result?.source === 'ebay';
  const [state, setState] = useState<ItemState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (isEbay) return;
    let cancelled = false;
    getItem(id, searched ?? undefined).then(
      (item) => {
        if (!cancelled) setState({ status: 'success', item });
      },
      (error: unknown) => {
        if (cancelled) return;
        const notFound = error instanceof ApiError && error.status === 404;
        const message = error instanceof ApiError ? error.message : FALLBACK_ERROR;
        setState({ status: 'error', notFound, message });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [id, isEbay, searched, attempt]);

  // A new page: start at the top, with focus on its heading for keyboard and screen readers.
  useEffect(() => {
    window.scrollTo({ top: 0 });
    headingRef.current?.focus();
  }, []);

  const item = state.status === 'success' ? state.item : null;
  const backLabel = result ? 'Back to results' : 'Back to search';
  const back = (
    <button type="button" className={styles.back} onClick={onBack}>
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="M10 3.5 5.5 8l4.5 4.5" />
      </svg>
      {backLabel}
    </button>
  );

  // Opened from a link or a reload, and the archive doesn't have it (e.g. an eBay item).
  if (!result && state.status === 'error' && state.notFound) {
    return (
      <article className={styles.details} aria-labelledby={titleId}>
        {back}
        <div className={styles.missing}>
          <h2 id={titleId} ref={headingRef} tabIndex={-1} className={styles.title}>
            This listing is no longer available
          </h2>
          <p>
            eBay listings are not stored, so they can only be opened from the current results.
            Please start a new search to find this listing again.
          </p>
        </div>
      </article>
    );
  }

  const title = result?.title ?? item?.title ?? 'Loading listing…';
  const imageUrl = result?.image_url ?? item?.image_url;
  const score = result ? Math.round(result.match_score) : null;
  const price = result?.price ?? null;

  return (
    <article className={styles.details} aria-labelledby={titleId}>
      {back}
      <div className={styles.layout}>
        <figure className={styles.polaroid}>
          {imageUrl ? (
            <img className={styles.image} src={imageUrl} alt={title} />
          ) : (
            <div className={`${styles.image} ${styles.placeholder}`} />
          )}
          {score !== null && (
            <span className={styles.stamp}>
              <span className={styles.stampLabel}>Match</span> <strong>{score}</strong>
              <span className="visually-hidden"> out of 100</span>
            </span>
          )}
        </figure>

        <div className={styles.info}>
          <span className={styles.source} data-source={isEbay ? 'ebay' : 'local'}>
            {isEbay ? 'eBay' : 'Archive (not for sale)'}
          </span>
          <h2 id={titleId} ref={headingRef} tabIndex={-1} className={styles.title}>
            {title}
          </h2>
          <p className={styles.price} data-missing={price === null || undefined}>
            {price === null ? 'Price unavailable' : usd.format(price)}
          </p>

          {result?.source === 'ebay' && result.listing_url && (
            <>
              <a
                className={styles.primary}
                href={result.listing_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                View listing on eBay
                <svg viewBox="0 0 16 16" aria-hidden="true">
                  <path d="M6.5 3.5h-3v9h9v-3M9 3.5h3.5V7M12.5 3.5 7 9" />
                </svg>
                <span className="visually-hidden"> (opens in a new tab)</span>
              </a>
              <p className={styles.note}>
                This listing is from eBay. Open it on eBay for size, condition, and shipping
                details.
              </p>
            </>
          )}

          {!isEbay && state.status === 'loading' && (
            <div className={styles.loading} aria-live="polite">
              <span className="visually-hidden">Loading listing details…</span>
              <span className={styles.line} />
              <span className={styles.line} data-short />
            </div>
          )}

          {!isEbay && state.status === 'error' && (
            <div className={styles.error} role="alert">
              <p>{state.message}</p>
              {!state.notFound && (
                <button
                  type="button"
                  className={styles.retry}
                  onClick={() => {
                    setState({ status: 'loading' });
                    setAttempt((n) => n + 1);
                  }}
                >
                  Retry
                </button>
              )}
            </div>
          )}

          {item && (
            <>
              <WhyItMatched item={item} searched={searched} />
              <DatasetFacts item={item} />
            </>
          )}
        </div>
      </div>
    </article>
  );
}
