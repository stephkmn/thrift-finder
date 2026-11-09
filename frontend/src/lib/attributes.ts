import type { Attributes, ScalarAttributeName } from '../api/types';

export const SCALAR_ATTRIBUTES: ScalarAttributeName[] = ['category', 'color', 'fabric', 'fit'];

/** Contract rule: no features is `null`, never `[]`. */
export function normalizeFeatures(features: string[] | null): string[] | null {
  return features && features.length > 0 ? features : null;
}

/** Same features in any order; null and [] both mean "none". */
export function sameFeatures(a: string[] | null, b: string[] | null): boolean {
  const left = new Set(a ?? []);
  const right = new Set(b ?? []);
  return left.size === right.size && [...left].every((feature) => right.has(feature));
}

export function sameAttributes(a: Attributes, b: Attributes): boolean {
  return SCALAR_ATTRIBUTES.every((name) => a[name] === b[name]) && sameFeatures(a.others, b.others);
}
