/**
 * API contract (S1-4, extended in S3-6). Mirrors the Pydantic models in backend/app/schemas.py
 * and docs/PHASE2_SPRINT_PLAN.md section 4.2. Change both sides in the same PR, per the plan.
 */

/** Attributes that always hold exactly one value. */
export type ScalarAttributeName = 'category' | 'color' | 'fabric' | 'fit';

export type AttributeName = ScalarAttributeName | 'others';

export interface Attributes {
  category: string; // e.g. "jacket"
  color: string; // e.g. "black"
  fabric: string; // e.g. "denim"
  fit: string; // e.g. "regular fit"
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

// POST /api/search (S2-5, S3-4, S3-7): live eBay listings with DATA_SOURCE=ebay, otherwise (or when
// eBay fails) the local archive. VITE_USE_MOCKS=true answers from src/api/mocks/ instead.
export interface SearchRequest {
  query_id: string;
  original_attributes: Attributes;
  edited_attributes: Attributes;
  text?: string;
}

export interface SearchResult {
  id: string;
  title: string;
  price: number | null; // USD; null for archive items and for eBay listings in another currency
  image_url: string;
  listing_url: string | null; // null for local archive items: they are not for sale
  source: 'ebay' | 'local';
  match_score: number; // 0–100 rescaled, per plan §4.3
}

export interface SearchResponse {
  results: SearchResult[]; // max 10
}

// GET /api/item/{id} (S3-6): details for an archive listing. Mirrors ItemDetails in
// backend/app/schemas.py. eBay listings are never stored, so they always return 404; the
// details page builds those from the search result instead.

/** The listing's labels exactly as the dataset has them (any may be missing). */
export interface DatasetLabels {
  type: string | null;
  category: string | null;
  colors: string[];
  material: string | null;
  cut: string | null;
  pattern: string | null;
  brand: string | null;
}

/** One searched attribute next to the listing's label, mapped onto our vocabulary. */
export interface AttributeComparison {
  attribute: 'category' | 'color' | 'fabric' | 'fit';
  yours: string;
  listing: string | null; // null when the dataset has no label for it
  match: boolean | null; // null when the label can't tell
}

export interface ItemDetails {
  id: string;
  title: string;
  image_url: string;
  source: 'local';
  dataset_labels: DatasetLabels;
  /** Empty unless the request passed the searched attributes as query parameters. */
  comparison: AttributeComparison[];
  /** CC BY 4.0 credit for the dataset photo, with a link to the dataset. */
  credit: { text: string; url: string };
}
