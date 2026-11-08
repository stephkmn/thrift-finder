import type { ScalarAttributeName } from '../api/types';
import attributesYaml from '../../../backend/app/ml/attributes.yaml';

/** The values the model can return for each attribute, in `attributes.yaml` order. */
export type Vocabulary = Record<ScalarAttributeName, string[]> & {
  /** Names of the yes/no `others` features, e.g. "hood". */
  features: string[];
};

const SCALARS: ScalarAttributeName[] = ['category', 'color', 'fabric', 'fit'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function fail(path: string): never {
  throw new Error(`attributes.yaml is missing or malformed at "${path}".`);
}

function stringList(value: unknown, path: string): string[] {
  if (!Array.isArray(value) || value.length === 0) fail(path);
  return value.map((item, index) => (typeof item === 'string' ? item : fail(`${path}[${index}]`)));
}

/** Checks the parsed YAML and pulls out the lists the UI needs. Throws naming the bad key. */
export function parseVocabulary(raw: unknown): Vocabulary {
  if (!isRecord(raw)) fail('(root)');
  const scalars = isRecord(raw.scalars) ? raw.scalars : fail('scalars');
  const others = isRecord(raw.others) ? raw.others : fail('others');
  const features = isRecord(others.features) ? others.features : fail('others.features');

  const lists = {} as Record<ScalarAttributeName, string[]>;
  for (const name of SCALARS) {
    const entry = isRecord(scalars[name]) ? scalars[name] : fail(`scalars.${name}`);
    lists[name] = stringList(entry.values, `scalars.${name}.values`);
  }
  const featureNames = Object.keys(features);
  if (featureNames.length === 0) fail('others.features');

  return { ...lists, features: featureNames };
}

export const VOCABULARY: Vocabulary = parseVocabulary(attributesYaml);
