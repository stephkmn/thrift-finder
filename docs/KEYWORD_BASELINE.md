# S3-3: Keyword-only retrieval baseline (Member B)

The baseline ranks the **same 500 local search listings** as the FashionCLIP system,
but uses **no image or text embeddings and no AI model**. This allows the team to
compare a simple lexical method against image-only and image-plus-edit retrieval.

## How it works

1. Convert edited attributes into positive search keywords using
   `backend/app/data/query_keywords.py` (S2-4). Alternatively supply raw keywords.
2. Normalize each listing's available metadata into a caption using the existing
   `backend/app/ml/index.py:listing_text` mapping (type, color, material, fit, pattern).
3. Tokenize both query and caption as lowercase alphanumeric words.
4. Rank by the **fraction of distinct query words present in the caption**; ties
   preserve listing order. Items matching no query words are omitted.

The JSON `coverage` value is a **0–100 query-token coverage percentage**. It is
**not** probability, P@10, or the FashionCLIP `match_score`, so those displayed
scores must not be compared directly. Use ranked results and the same manually
labeled evaluation queries to compute the evaluation metrics.

## Run from repository root

```bash
python -m scripts.keyword_baseline --query "brown leather jacket" --top-k 10
python -m scripts.keyword_baseline --category jacket --color brown --fabric leather --top-k 10
python -m scripts.keyword_baseline --query "brown leather jacket" --out data/keyword_baseline.json
```

`--listings` optionally points at a different JSONL fixture. Output JSON includes the
query, method identifier, listing count, and ranked IDs/titles with matched terms.
Run tests with `python -m pytest backend/tests/test_keyword_baseline.py -q`.

## Limitations / S3-3 evaluation handoff

- This is a **keyword-only baseline**, not the live eBay connector or `/api/search`.
- Metadata may be incomplete or imperfect. `others` features (e.g. hood) generally
  lack labels in the fallback dataset; feature satisfaction is **not scored**.
- Negative phrases such as `no hood` are excluded from positive keywords by the
  existing S2-4 builder; absence constraints are **not enforced** by this baseline.
- No relevance metrics are claimed yet. Member A's seeded 38-query evaluation set,
  relevance judgments, and `scripts/evaluate.py` are required to report P@10 and
  edit-satisfaction for keyword-only vs. image-only vs. image-with-edits.
- Search only `data/listings.jsonl` (the **train** split); never include
  `data/eval/dataset/` query images in the candidate pool.
