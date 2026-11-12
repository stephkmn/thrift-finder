# Data sources and integration — CECS 451 Phase 2

## Licensed fallback dataset

- **Source:** Farrukh Nauman, [fashion-second-hand-front-only-rgb](https://huggingface.co/datasets/fnauman/fashion-second-hand-front-only-rgb) (front-image subset of the Second-Hand Fashion dataset).
- **Original reference:** Nauman, F. (2024). *Clothing Dataset for Second-Hand Fashion (Version 3)*. Zenodo. https://doi.org/10.5281/zenodo.13788681
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0), as identified on the dataset card and Zenodo release. Attribute the author and source when presenting results. Images here are resized JPEG derivatives of the source photographs; the resized format is a modification.
- **Intended use:** Local demonstration and evaluation of outerwear search. **These garments are not live listings and are not for sale.** Price information in the dataset is a rough price category, not a verified current USD price, and no purchase URLs are available.
- **Access:** Hugging Face `datasets` library with `streaming=True`. The searchable index uses the `train` split; the separately stored evaluation pool uses `test`. The first use requires internet access, and remote dataset shards may still be downloaded/cached.
- **Subset:** Garment type labels containing `jacket`, `coat`, `blazer`, `parka`, `windbreaker`, `anorak`, `vest`, or `gilet`. The actual count is reported by the ingestion script; the target is 500. The script skips unreadable photos and deduplicates exact processed-image matches.
- **Other fields:** `type`, `category`, `colors`, `material`, `cut`, `pattern`, `brand`, and the original `price` range are retained where available. Some source labels are missing; the script does not invent them.

### Ingestion Results — November 6, 2026

- Dataset: fnauman/fashion-second-hand-front-only-rgb
- Source: Hugging Face
- License: CC BY 4.0
- Dataset split: train
- Source revision: main (not yet pinned)
- Total records scanned: 8,353
- Outerwear records accepted: 500
- Invalid images: 0
- Exact duplicate images: 0
- Total records saved: 500
- Image format: JPEG
- Image maximum dimensions: 512 x 512
- Metadata format: JSONL

The ingestion pipeline successfully collected 500 outerwear
images and their associated attributes. These include
clothing types, colors, materials, patterns, and other
available metadata.

The records are stored locally in data/listings.jsonl,
with images saved in data/images/.

This dataset contains archival secondhand clothing rather
than active marketplace listings. Therefore, actual
purchase links and verified sale prices are unavailable.

## Preprocessing and normalized records (S3-9)

The transformation is implemented in `scripts/ingest.py` and
`backend/app/data/preprocess.py`. For each streamed source row:

1. **Select by garment type.** Keep labels containing a whole-word match for
   `jacket`, `coat`, `blazer`, `parka`, `windbreaker`, `anorak`, `vest`, or `gilet`
   (case-insensitive). This is a **label-based filter**, not a visual clothing
   classifier. Incorrect source labels can admit non-outerwear items.
2. **Normalize the image.** Correct EXIF orientation, convert to RGB, preserve
   aspect ratio while limiting the longest side to 512 pixels, and save a JPEG
   (quality 85, optimized). The originals are not written to the project.
3. **Skip duplicates and unreadable images.** Hash the resulting JPEG bytes with
   SHA-256 and skip exact matches **within the current ingestion run**. This
   does not detect near duplicates or guarantee no train/test visual overlap.
4. **Normalize metadata.** Collapse repeated whitespace; turn known empty
   markers into `null`; parse color lists (including string-encoded lists),
   remove repeated colors case-insensitively, and preserve the available source
   labels rather than inferring attributes from photographs.
5. **Record provenance.** Build an ID (`secondhand-` plus the zero-padded
   zero-based row index) and store `dataset_id`, `source_index`, and a relative
   `image_path`. A `source_index` is meaningful **within its dataset split**;
   it is not a globally unique source listing identifier.

The JSONL output has one record per garment. The main fields are:

| Field | Meaning |
|---|---|
| `id`, `title`, `source` | Local result identifier, label-based title, and `"local"` provenance |
| `dataset_id`, `source_index` | Hugging Face dataset ID and original split row position |
| `image_path` | Repository-relative local JPEG path; **not** a public URL |
| `attributes` | Available `type`, `category`, `colors`, `material`, `cut`, `pattern`, and `brand` |
| `price_band` | Original categorical/range price label, if present |
| `price`, `listing_url` | Always `null` for archival garments; no verified live price or purchase link |

The loader (`backend/app/data/local_dataset.py`) rejects malformed JSON,
missing mandatory fields, unsafe paths, and missing images by default, and
skips repeated record IDs. The importer does **not** create embedding vectors;
`python -m scripts.build_embeddings` creates the local image/text index after
successful ingestion. Rebuild the index if the indexed dataset or model changes.

### Data provenance, reproducibility, and retention

- The train and test splits are ingested into separate directories. Use the
  **train split for retrieval** and the **test split for evaluation**, without
  copying query photos into the search corpus.
- Recorded runs used source revision `main`, which is **not pinned**. A fresh
  run may differ if the upstream dataset changes. For a fixed revision, pass
  `--revision <HF_COMMIT_SHA>` and record the commit plus run counts.
- Both the local dataset and generated embeddings stay under gitignored
  `data/`. Only code, allowable sample images, and evaluation metadata are
  committed. CC BY 4.0 attribution still applies when redisplaying dataset
  images; resizing is a modification to disclose.
- User-uploaded query photos must stay in memory and must not be written to
  dataset files or application logs. The evaluation exceptions and credited
  sample photos are described under **Privacy and evaluation** below.
- Live eBay data is **not part of this licensed fallback dataset**. The
  separate S1-1 eBay PR documents the approved no-persistence exemption and
  the standalone API feasibility client. Do not silently import eBay results
  into the local index or retain them in persistent caches.

## Reproduce the local fallback dataset

From the repository root, with Python 3.11 activated:

```bash
python -m pip install -e ".[dev,data]"
# Optional quick smoke run (rewrites train metadata with 25 records):
python scripts/ingest.py --split train --limit 25
# Full local search corpus; re-run after the smoke test:
python scripts/ingest.py --split train --limit 500
# Evaluation pool: separate test split, not part of the search index:
python scripts/ingest.py --split test --limit 300
# Build 500 listing embeddings after ingesting the full train split:
python -m scripts.build_embeddings --batch-size 16
# Validate local metadata and image files:
python -c "from backend.app.data.local_dataset import load_listings; print(len(load_listings()), 'listings valid')"
pytest backend/tests -q
ruff check backend/ scripts/
```

The script writes:

- `data/listings.jsonl` — one normalized JSON object per garment.
- `data/images/secondhand-*.jpg` — resized garment images.

Both paths should stay **gitignored**. The script prints counts of rows scanned, outerwear found, invalid images, duplicates, and saved garments. Optionally use `--revision <HF_COMMIT_SHA>` to pin a specific source version and record that revision in this document.

### Separate evaluation pool (`test` split)

Run `python scripts/ingest.py --split test --limit 300` to import the **test split only**. This
writes to `data/eval/dataset/listings.jsonl` and `data/eval/dataset/images/`, without
changing the original `data/listings.jsonl` or `data/images/` used for search.

The S1-11 evaluation plan reports a pool of **212 eligible test-split outerwear photos**
(`docs/EVALUATION.md`); `--limit 300` is a ceiling, **not** an expectation of 300 saved
images. The importer may warn that fewer than 300 were saved. Record the actual count
from your run. The separate 30-photo, seed-451 selection is a **later sampling step**, owned
by Member D with Member A according to the sprint plan; this importer does not select
those 30 or generate the evaluation CSV files. That step is `scripts/build_eval_set.py`,
which reads `data/eval/dataset/listings.jsonl` and downloads nothing itself.

#### Evaluation pool ingestion results — November 12, 2026

- Command: `python scripts/ingest.py --split test --limit 300`
- Source revision: main (not yet pinned)
- Total test-split rows scanned: 3,390
- Outerwear records found: 212
- Invalid images: 0
- Exact duplicate images skipped: 1 (a Blazer)
- Total records saved: **211** (Jacket 114, Blazer 40, Vest 37, Winter Jacket 15, Rain Jacket 3,
  Denim Jacket 2)
- The "fewer than the requested count" warning is expected: 211 is the whole eligible pool.

#### Known issue: garment types are sometimes wrong

Building the S1-11 evaluation set found that the dataset's `type` label is unreliable for
**"Blazer"**: of 11 test-split "Blazer" photos inspected, 5 were not outerwear (a lace blouse, a
striped T-shirt, a floral top, jeans, trousers). The 24 inspected photos of the other outerwear
types were all correct. The search index filters on the same label, so its listings typed "Blazer"
(train split) likely include some non-outerwear, and a search can return them. Possible fixes: a quick
visual check of the indexed "Blazer" listings, or dropping that type from the index until checked.
The evaluation set handles it with `eval/excluded.csv` (see `docs/EVALUATION.md`).

The `source_index` in each JSONL record is the original row position within its split,
which the sampling script can use to identify the test photo. All evaluation photos are
local, gitignored files; only permitted evaluation labels and code should be committed.

### Local result API integration

The current `SearchResult` API schema allows `price: float | None` and
`listing_url: str | None`, so the local archive correctly uses `null` for both.
The backend must still turn a local `image_path` into a usable `image_url` for the
frontend; local filesystem paths are not public web URLs. Coordinate with the
Backend and Frontend Leads, and **do not fabricate prices or purchase links**.

FashionCLIP embedding/index generation is implemented separately in
`scripts/build_embeddings.py` and `backend/app/ml/`. This ingestion pipeline
provides photographs and metadata; it does not generate vectors itself.

## Planned eBay API integration

- eBay Browse API, using developer authentication and permission appropriate to the target environment.
- Status: not implemented in this data pipeline PR; exact access and allowed fields must be verified independently.
- Credentials must be stored only in environment variables / a local ignored `.env` file, never in Git.
- Data limits, permissible retention and caching, and redistribution rules must be checked before saving retrieved listing data.


### S1-1 — eBay Developer Access Status

**Date:** November 11, 2026

**Status:** Pending developer account approval

#### Progress

- Registered for the eBay Developers Program.
- Received confirmation that the account is under review.
- eBay states that approval takes at least one business day.
- Sandbox and Production credentials are not yet available.
- OAuth authentication and Browse API access have not been tested.

#### Current Blocker

The developer account is awaiting approval from eBay.
API testing cannot proceed until account access is granted.

#### Current Approach

The prototype will continue using the licensed local
secondhand clothing dataset with 500 indexed garments.

This provides a reliable search dataset while live
marketplace API access remains unverified.

#### Next Steps

1. Wait for eBay developer account approval.
2. Obtain Sandbox credentials.
3. Test OAuth authentication.
4. Check Production Browse API eligibility.
5. Update the documentation with actual test results.


## Privacy and evaluation

- The ingestion script handles third-party licensed dataset images, not user uploads. Query images should be processed in memory and not permanently saved, per the Phase 1 promise.
- Query photos must never also be in the search corpus, because that artificially inflates retrieval accuracy. The S1-11 evaluation set therefore takes its dataset queries from the **`test` split only**; the search index is built from `train` (`scripts/ingest.py`). See `docs/DECISIONS.md` and `docs/EVALUATION.md` → S1-11 evaluation set.
- Dataset query images are re-downloadable by split and row index, so they are not committed; they live under the gitignored `data/eval/`. Only labels (`eval/*.csv`) are committed, and the dataset is credited (CC BY 4.0) wherever results are shown.
- Member D's own photos are kept local under `data/eval/own/`, except the three in `samples/`, which are committed with location (EXIF GPS) data removed and no faces in frame.
- Evaluate the 38 queries (photo alone versus photo with edited attributes), plus manually labeled top-10 relevance; document results, latency, and failures in `docs/EVALUATION.md` alongside the ML Lead.