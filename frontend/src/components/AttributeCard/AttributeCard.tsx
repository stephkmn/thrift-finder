import type { AttributeName, ExtractResponse } from '../../api/types';
import styles from './AttributeCard.module.css';

interface AttributeCardProps {
  result: ExtractResponse;
}

const ATTRIBUTES: { name: AttributeName; label: string }[] = [
  { name: 'category', label: 'Category' },
  { name: 'color', label: 'Color' },
  { name: 'fabric', label: 'Fabric' },
  { name: 'fit', label: 'Fit' },
  { name: 'hood', label: 'Hood' },
];

// Below this the model is close to guessing; shown with a quieter bar (the % text still carries it).
const LOW_CONFIDENCE = 0.6;

/** Read-only view of extracted attributes. S2-6 builds the attribute editor on top of this. */
export function AttributeCard({ result }: AttributeCardProps) {
  return (
    <section className={styles.card} aria-labelledby="attribute-card-title">
      <h2 id="attribute-card-title" className={styles.title}>
        What we found
      </h2>
      <dl className={styles.list}>
        {ATTRIBUTES.map(({ name, label }) => {
          const confidence = result.confidences[name];
          const percent = Math.round(confidence * 100);
          return (
            <div key={name} className={styles.row}>
              <dt className={styles.name}>{label}</dt>
              <dd className={styles.value}>{result.attributes[name]}</dd>
              <dd className={styles.confidence}>
                <span
                  className={styles.bar}
                  data-low={confidence < LOW_CONFIDENCE || undefined}
                  aria-hidden="true"
                >
                  <span style={{ width: `${percent}%` }} />
                </span>
                <span className={styles.percent}>
                  {percent}%<span className="visually-hidden"> confidence</span>
                </span>
              </dd>
            </div>
          );
        })}
      </dl>
      <p className={styles.queryId}>
        Query ID: <code>{result.query_id}</code>
      </p>
    </section>
  );
}
