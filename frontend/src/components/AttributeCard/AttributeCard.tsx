import type { ExtractResponse, ScalarAttributeName } from '../../api/types';
import styles from './AttributeCard.module.css';

interface AttributeCardProps {
  result: ExtractResponse;
}

const SCALAR_ATTRIBUTES: { name: ScalarAttributeName; label: string }[] = [
  { name: 'category', label: 'Category' },
  { name: 'color', label: 'Color' },
  { name: 'fabric', label: 'Fabric' },
  { name: 'fit', label: 'Fit' },
];

// Below this the model is close to guessing: quieter bar plus a "Double-check" note.
const LOW_CONFIDENCE = 0.6;

function toPercent(confidence: number): number {
  return Math.round(confidence * 100);
}

/** Read-only view of extracted attributes. S2-6 builds the attribute editor on top of this. */
export function AttributeCard({ result }: AttributeCardProps) {
  // The contract says "nothing found" is null; treat a stray [] the same way.
  const others = result.attributes.others?.length ? result.attributes.others : null;

  return (
    <section className={styles.card} aria-labelledby="attribute-card-title">
      <h2 id="attribute-card-title" className={styles.title}>
        What we found
      </h2>
      <dl className={styles.list}>
        {SCALAR_ATTRIBUTES.map(({ name, label }) => {
          const confidence = result.confidences[name];
          const percent = toPercent(confidence);
          const isLow = confidence < LOW_CONFIDENCE;
          return (
            <div key={name} className={styles.row}>
              <dt className={styles.name}>{label}</dt>
              <dd className={styles.value}>
                {result.attributes[name]}
                {isLow && <span className={styles.check}>Double-check</span>}
              </dd>
              <dd className={styles.confidence}>
                <span className={styles.bar} data-low={isLow || undefined} aria-hidden="true">
                  <span style={{ width: `${percent}%` }} />
                </span>
                <span className={styles.percent}>
                  {percent}%<span className="visually-hidden"> confidence</span>
                </span>
              </dd>
            </div>
          );
        })}
        <div className={styles.row}>
          <dt className={styles.name}>Other features</dt>
          <dd className={styles.others}>
            {others ? (
              <ul className={styles.chips}>
                {others.map((feature) => {
                  const confidence = result.confidences.others?.[feature];
                  const isLow = confidence !== undefined && confidence < LOW_CONFIDENCE;
                  return (
                    <li key={feature} className={styles.chip} data-low={isLow || undefined}>
                      <span className={styles.chipName}>{feature}</span>
                      {confidence !== undefined && (
                        <span className={styles.chipPercent}>
                          {toPercent(confidence)}%
                          <span className="visually-hidden">
                            {' '}
                            confidence{isLow ? ', double-check' : ''}
                          </span>
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <span className={styles.none}>None detected</span>
            )}
          </dd>
        </div>
      </dl>
      <p className={styles.queryId}>
        Query ID: <code>{result.query_id}</code>
      </p>
    </section>
  );
}
