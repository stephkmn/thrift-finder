# Data sources and integration — CECS 451 Phase 2

## Licensed fallback dataset

- **Source:** Farrukh Nauman, [fashion-second-hand-front-only-rgb](https://huggingface.co/datasets/fnauman/fashion-second-hand-front-only-rgb) (front-image subset of the Second-Hand Fashion dataset).
- **Original reference:** Nauman, F. (2024). *Clothing Dataset for Second-Hand Fashion (Version 3)*. Zenodo. https://doi.org/10.5281/zenodo.13788681
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0), as identified on the dataset card and Zenodo release. Attribute the author and source when presenting results. Images here are resized JPEG derivatives of the source photographs; the resized format is a modification.
- **Intended use:** Local demonstration and evaluation of outerwear search. **These garments are not live listings and are not for sale.** Price information in the dataset is a rough price category, not a verified current USD price, and no purchase URLs are available.
- **Access:** Hugging Face `datasets` library with `streaming=True`, using the `train` split. The first use requires an internet connection, and remote dataset shards may still be downloaded/cached.
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

## Reproduce the local fallback dataset

From the repository root, with Python 3.11 activated:

```bash
python -m pip install -e ".[dev,data]"
python scripts/ingest.py --limit 25
python scripts/ingest.py --limit 500
pytest backend/tests -q
ruff check backend/ scripts/
```

The script writes:

- `data/listings.jsonl` — one normalized JSON object per garment.
- `data/images/secondhand-*.jpg` — resized garment images.

Both paths should stay **gitignored**. The script prints counts of rows scanned, outerwear found, invalid images, duplicates, and saved garments. Optionally use `--revision <HF_COMMIT_SHA>` to pin a specific source version and record that revision in this document.

### Known integration mismatch to coordinate

The existing `SearchResult` API schema requires `price: float`, `image_url: str`, and `listing_url: str`. The archival dataset **has no live numeric sale price or listing URL**, and the local saved image path is not a public URL. The Backend Lead must decide how to represent demo-only results (e.g., an explicit data-source/demo flag and optional price/link, or a separate demo view). **Do not fabricate eBay prices or purchase links.** This change must be coordinated with the frontend TypeScript contract.

The ML Lead will generate and cache image/text embeddings separately using FashionCLIP; the ingestion pipeline produces the local images and metadata, not embeddings or similarity scores.

## Planned eBay API integration

- eBay Browse API, using developer authentication and permission appropriate to the target environment.
- Status: not implemented in this data pipeline PR; exact access and allowed fields must be verified independently.
- Credentials must be stored only in environment variables / a local ignored `.env` file, never in Git.
- Data limits, permissible retention and caching, and redistribution rules must be checked before saving retrieved listing data.

## Privacy and evaluation

- The ingestion script handles third-party licensed dataset images, not user uploads. Query images should be processed in memory and not permanently saved, per the Phase 1 promise.
- For the Phase 2 demo, use team-owned query photographs or other appropriately licensed query images. Avoid selecting the exact same images as both query and search corpus in formal evaluation because it artificially inflates retrieval accuracy.
- Evaluate ~15–20 queries (photo alone versus photo with edited attributes), plus manually labeled top-10 relevance; document results, latency, and failures in `docs/EVALUATION.md` alongside the ML Lead.