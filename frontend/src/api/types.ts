/**
 * DRAFT API contract (S1-4) — mirrors docs/PHASE2_SPRINT_PLAN.md §4.2.
 * Members A (ML) and C (Backend) must confirm these against the Pydantic schemas.
 * Change only via PR, per the plan.
 */

/** Attributes that always hold exactly one value. */
export type ScalarAttributeName = 'category' | 'color' | 'fabric' | 'fit';

export type AttributeName = ScalarAttributeName | 'others';

export interface Attributes {
  category: string; // e.g. "jacket"
  color: string; // e.g. "black"
  fabric: string; // e.g. "denim"
  fit: string; // e.g. "regular"
  /**
   * Any other features found, e.g. ["hood", "pockets"].
   * `null` when nothing was found — never an empty array.
   */
  others: string[] | null;
}

export interface Confidences {
  category: number; // each 0–1
  color: number;
  fabric: number;
  fit: number;
  /**
   * One 0–1 score per feature in `attributes.others`, keyed by feature name,
   * e.g. { hood: 0.82, pockets: 0.64 }. `null` exactly when `attributes.others` is null.
   */
  others: Record<string, number> | null;
}

export interface ExtractResponse {
  attributes: Attributes;
  confidences: Confidences;
  query_id: string;
}

// Defined now so Sprint 2 is ready; not used by the skeleton UI yet.
export interface SearchRequest {
  query_id: string;
  original_attributes: Attributes;
  edited_attributes: Attributes;
  text?: string;
}

export interface SearchResult {
  id: string;
  title: string;
  price: number; // DRAFT: assumed USD number — confirm with C
  image_url: string;
  listing_url: string;
  source: 'ebay' | 'local';
  match_score: number; // 0–100 rescaled, per plan §4.3
}

export interface SearchResponse {
  results: SearchResult[]; // max 10
}
