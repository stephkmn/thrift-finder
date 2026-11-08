import { useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { Attributes, ExtractResponse, ScalarAttributeName } from '../../api/types';
import {
  normalizeFeatures,
  SCALAR_ATTRIBUTES,
  sameAttributes,
  sameFeatures,
} from '../../lib/attributes';
import { swatchBackground } from '../../lib/colorSwatches';
import { VOCABULARY } from '../../lib/vocabulary';
import styles from './AttributeEditor.module.css';

interface AttributeEditorProps {
  /** The extract response: the model's attributes, confidences, and query id. */
  extracted: ExtractResponse;
  /** The current edits. */
  value: Attributes;
  onChange: (next: Attributes) => void;
  /** Actions under the editor, e.g. the Update results button. */
  children?: ReactNode;
}

// Below this the model is close to guessing, so we ask the user to double-check.
const LOW_CONFIDENCE = 0.6;

const LABELS: Record<ScalarAttributeName, string> = {
  category: 'Category',
  color: 'Color',
  fabric: 'Fabric',
  fit: 'Fit',
};

/**
 * Vocabulary values, with any value the API sent that the vocabulary lacks kept at the front
 * so it is shown as it is instead of being silently replaced.
 */
function optionsFor(name: ScalarAttributeName, ...current: string[]): string[] {
  const vocabulary = VOCABULARY[name];
  const extras = current.filter(
    (value, i) => !vocabulary.includes(value) && current.indexOf(value) === i,
  );
  return [...extras, ...vocabulary];
}

function describeFeatures(features: string[] | null): string {
  return features?.length ? features.join(', ') : 'none';
}

interface RowProps {
  label: string;
  /** Reset button target, e.g. "color" gives "Reset color". */
  name: string;
  /** Set when the user changed this attribute: what the model said. */
  was: string | null;
  needsCheck: boolean;
  onReset: () => void;
  /** Group controls (radios, chips) get a fieldset; a single select gets a label. */
  group?: boolean;
  controlId?: string;
  children: ReactNode;
}

function Row({ label, name, was, needsCheck, onReset, group, controlId, children }: RowProps) {
  const heading = (
    <span className={styles.name}>
      {label}
      {needsCheck && <span className={styles.check}>Double-check</span>}
    </span>
  );
  const meta = was !== null && (
    <span className={styles.meta}>
      <span className={styles.was}>was {was}</span>
      <button type="button" className={styles.reset} onClick={onReset} aria-label={`Reset ${name}`}>
        Reset
      </button>
    </span>
  );

  if (group) {
    return (
      <fieldset className={styles.row} data-edited={was !== null || undefined}>
        <legend className={styles.legend}>{heading}</legend>
        {meta}
        <div className={styles.control}>{children}</div>
      </fieldset>
    );
  }
  return (
    <div className={styles.row} data-edited={was !== null || undefined}>
      <label htmlFor={controlId} className={styles.legend}>
        {heading}
      </label>
      {meta}
      <div className={styles.control}>{children}</div>
    </div>
  );
}

function ColorPicker({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (color: string) => void;
}) {
  const groupName = useId();
  return (
    <div className={styles.swatches}>
      {options.map((color) => (
        <label key={color} className={styles.swatchOption}>
          <input
            type="radio"
            className={`visually-hidden ${styles.swatchInput}`}
            name={groupName}
            value={color}
            checked={value === color}
            onChange={() => onChange(color)}
          />
          <span
            className={styles.swatch}
            style={{ background: swatchBackground(color) }}
            aria-hidden="true"
          />
          <span className={styles.swatchName}>{color}</span>
        </label>
      ))}
    </div>
  );
}

function FeatureChips({
  value,
  lowConfidence,
  onChange,
}: {
  value: string[] | null;
  /** Features to flag because the model was unsure of them. */
  lowConfidence: Set<string>;
  onChange: (features: string[] | null) => void;
}) {
  const selectId = useId();
  const [pending, setPending] = useState('');
  const selectRef = useRef<HTMLSelectElement>(null);
  const features = value ?? [];
  const available = VOCABULARY.features.filter((feature) => !features.includes(feature));

  const remove = (feature: string) => {
    onChange(normalizeFeatures(features.filter((f) => f !== feature)));
    // The chip (and its focused button) is gone; keep focus in the same row.
    selectRef.current?.focus();
  };

  const add = () => {
    if (!pending) return;
    onChange([...features, pending]);
    setPending('');
  };

  return (
    <>
      {features.length > 0 ? (
        <ul className={styles.chips}>
          {features.map((feature) => {
            const isLow = lowConfidence.has(feature);
            return (
              <li key={feature} className={styles.chip} data-low={isLow || undefined}>
                <span className={styles.chipName}>{feature}</span>
                {isLow && <span className={styles.chipCheck}>Double-check</span>}
                <button
                  type="button"
                  className={styles.remove}
                  aria-label={`Remove ${feature}`}
                  onClick={() => remove(feature)}
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="m4.5 4.5 7 7m0-7-7 7" />
                  </svg>
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className={styles.none}>None</p>
      )}
      {available.length > 0 && (
        <div className={styles.add}>
          <label htmlFor={selectId} className="visually-hidden">
            Add feature
          </label>
          <select
            ref={selectRef}
            id={selectId}
            className={styles.select}
            value={pending}
            onChange={(event) => setPending(event.target.value)}
          >
            <option value="">Add a feature…</option>
            {available.map((feature) => (
              <option key={feature} value={feature}>
                {feature}
              </option>
            ))}
          </select>
          <button type="button" className={styles.addButton} onClick={add} disabled={!pending}>
            Add
          </button>
        </div>
      )}
    </>
  );
}

/** Lets the user correct the extracted attributes before searching (S2-6). */
export function AttributeEditor({ extracted, value, onChange, children }: AttributeEditorProps) {
  const original = extracted.attributes;
  const confidences = extracted.confidences;
  const ids = useId();
  const isEdited = !sameAttributes(value, original);

  const set = <K extends keyof Attributes>(name: K, next: Attributes[K]) =>
    onChange({ ...value, [name]: next });

  const scalarRow = (name: ScalarAttributeName) => {
    const changed = value[name] !== original[name];
    const common = {
      label: LABELS[name],
      name,
      was: changed ? original[name] : null,
      needsCheck: !changed && confidences[name] < LOW_CONFIDENCE,
      onReset: () => set(name, original[name]),
    };
    const options = optionsFor(name, value[name], original[name]);

    if (name === 'color') {
      return (
        <Row key={name} {...common} group>
          <ColorPicker value={value.color} options={options} onChange={(c) => set('color', c)} />
        </Row>
      );
    }
    const controlId = `${ids}-${name}`;
    return (
      <Row key={name} {...common} controlId={controlId}>
        <select
          id={controlId}
          className={styles.select}
          value={value[name]}
          onChange={(event) => set(name, event.target.value)}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </Row>
    );
  };

  const featuresChanged = !sameFeatures(value.others, original.others);
  const lowFeatures = new Set(
    featuresChanged
      ? []
      : Object.entries(confidences.others ?? {})
          .filter(([, score]) => score < LOW_CONFIDENCE)
          .map(([feature]) => feature),
  );

  return (
    <section className={styles.editor} aria-labelledby={`${ids}-title`}>
      <div className={styles.header}>
        <h2 id={`${ids}-title`} className={styles.title}>
          What we found
        </h2>
        <button
          type="button"
          className={styles.resetAll}
          onClick={() => onChange(original)}
          disabled={!isEdited}
        >
          Reset all
        </button>
      </div>
      <p className={styles.hint}>Change anything we got wrong, then update your results.</p>

      <div className={styles.rows}>
        {SCALAR_ATTRIBUTES.map(scalarRow)}
        <Row
          label="Other features"
          name="other features"
          was={featuresChanged ? describeFeatures(original.others) : null}
          needsCheck={false}
          onReset={() => set('others', original.others)}
          group
        >
          <FeatureChips
            value={value.others}
            lowConfidence={lowFeatures}
            onChange={(features) => set('others', features)}
          />
        </Row>
      </div>

      {children && <div className={styles.actions}>{children}</div>}
    </section>
  );
}
