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

### Search-result contract and remaining integration

The `SearchResult` API schema supports `price: float | None`, `image_url: str`, `listing_url: str | None`, and `source: "ebay" | "local"`. This allows local archival items to have no verified sale price or purchase link.

The local dataset contains no live purchase URLs or verified USD prices, so these fields must remain `null` when unavailable. Local image paths also need to be exposed through an appropriate backend image-serving route before they can be displayed in the frontend. **Do not fabricate eBay prices or purchase links.**

The schema also requires a `match_score` between 0 and 100. The standalone eBay client does not generate FashionCLIP similarity scores, so score generation and mapping must be coordinated with the Backend and ML Leads.

The ML pipeline generates and caches image/text embeddings separately using FashionCLIP. The ingestion pipeline produces local images and metadata, not similarity scores.

## eBay API integration status

The eBay Browse API has been successfully tested in both Sandbox and Production environments.

A reusable, read-only API client is implemented in `backend/app/data/ebay_client.py`, with a command-line preview in `scripts/ebay_preview.py`.

The client supports:

- OAuth 2.0 application authentication using environment-specific developer credentials.
- Searching live eBay listings through the Browse API.
- Filtering for used clothing with `conditions:{USED}`.
- Extracting listing IDs, titles, prices, currencies, conditions, images, and eBay listing URLs.
- Returning normalized listing information without persistent storage.
- Controlled error handling for authentication, networking, and API response failures.

The client is currently a standalone integration prototype. **It has not yet been connected to the application's `/api/search` endpoint or frontend.** This integration must be coordinated with the Backend Lead.

The licensed local dataset of 500 indexed garments remains the reliable search fallback.

API credentials must be provided through environment variables or secure runtime prompts. Credentials, OAuth tokens, and eBay API responses must not be committed to Git or written to persistent storage.

## S1-1 — eBay Developer Access and Feasibility

**Last verified:** November 12, 2026

**Status:** Sandbox and Production API access verified successfully.

### Developer Account and Compliance

- Registered for and received approval from the eBay Developers Program.
- Obtained Sandbox and Production application credentials.
- Received a Marketplace Account Deletion notification exemption based on not persisting eBay data.
- Successfully authenticated against both environments using OAuth 2.0 client credentials.
- Verified that access tokens were issued with a lifetime of 7,200 seconds.

### Sandbox Verification

- Successfully authenticated against the Sandbox OAuth endpoint.
- Successfully called the Sandbox Browse API.
- Search query: `denim jacket`.
- Results returned: 1.

### Production Verification

- Successfully authenticated against the Production OAuth endpoint.
- Successfully called the live Browse API.
- Search query: `denim jacket`.
- Results returned: 3.

A second Production search used the query `brown leather jacket` with a requested limit of 5.

- Results returned: 5.
- All 5 listings contained titles, prices, conditions, image URLs, and eBay listing URLs.
- Only 1 result was pre-owned; the other 4 were classified as new with tags.

These results motivated the implementation of a used-only condition filter.

### Used-Only Search Verification

**Date:** November 12, 2026

- Environment: Production
- Query: `brown leather jacket`
- Filter: `conditions:{USED}`
- Requested limit: 5
- Results returned: 5
- All five results were classified as pre-owned.
- All five contained titles, prices, conditions, image URLs, and eBay listing URLs.

The test confirmed that the used-condition filter works and that the API returns the fields required for Thrift Finder.

The client processes results in memory without persisting live listing records. Exact listing titles, prices, and URLs are intentionally omitted from committed documentation.

Keyword search does not guarantee an exact match for every requested attribute. FashionCLIP reranking may help improve relevance in future integration.

### Automated Testing

The reusable eBay client was tested with mocked API responses.

- 11 eBay client unit tests passed.
- Full backend test suite passed, with 1 existing skipped test.
- Ruff linting passed.
- Live Production search succeeded with used-only filtering enabled.

### Privacy and Limitations

The application received an exemption from Marketplace Account Deletion notifications on the basis that it does not persist eBay data.

The current eBay client and preview script retrieve listings in memory without writing API responses, tokens, or listing records to files or a database. Future integration must preserve this behavior unless the application's compliance configuration is updated.

Successful Production API requests demonstrate technical access at the time of testing but do not independently establish that all applicable eBay partnership or production-use requirements have been satisfied.

The standalone client has not yet been integrated with FashionCLIP ranking or the application's search endpoint.

### Next Steps

1. Coordinate with the Backend Lead before connecting the eBay client to `/api/search`.
2. Preserve the 500-item local fallback dataset.
3. Ensure live eBay results are handled in memory without persistent storage.
4. Validate image, price, condition, and link fields during integration.
5. Review applicable eBay production-use requirements before deployment.
6. Test API failures and verify local fallback behavior.

See `docs/EBAY_FEASIBILITY.md` for additional verification details and reproduction commands.

## Privacy and evaluation

- The ingestion script handles third-party licensed dataset images, not user uploads. Query images should be processed in memory and not permanently saved, per the Phase 1 promise.
- Query photos must never also be in the search corpus, because that artificially inflates retrieval accuracy. The S1-11 evaluation set therefore takes its dataset queries from the **`test` split only**; the search index is built from `train` (`scripts/ingest.py`). See `docs/DECISIONS.md` and `docs/EVALUATION.md` → S1-11 evaluation set.
- Dataset query images are re-downloadable by split and row index, so they are not committed; they live under the gitignored `data/eval/`. Only labels (`eval/*.csv`) are committed, and the dataset is credited (CC BY 4.0) wherever results are shown.
- Member D's own photos are kept local under `data/eval/own/`, except the three in `samples/`, which are committed with location (EXIF GPS) data removed and no faces in frame.
- Evaluate the 38 queries (photo alone versus photo with edited attributes), plus manually labeled top-10 relevance; document results, latency, and failures in `docs/EVALUATION.md` alongside the ML Lead.