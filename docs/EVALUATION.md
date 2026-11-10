# Evaluation

## S1-5: zero-shot attribute extraction (preliminary)

**Date:** Nov 7, 2026 · **Owner:** Member A · **Script:** `scripts/zero_shot_accuracy.py`

FashionCLIP (`patrickjohncyh/fashion-clip`, primary) vs. base CLIP (`openai/clip-vit-base-patch32`,
baseline), both zero-shot with the vocabulary and prompts in `backend/app/ml/attributes.yaml`.
Image only, no text description.

| Attribute | n | fashion-clip | clip-vit-base-patch32 |
|---|---|---|---|
| category | 16 | 44% | 25% |
| color | 14 | 71% | 57% |
| fabric | 9 | 78% | 33% |
| others precision | 8 | 50% | 38% |
| others recall | 8 | 75% | 83% |
| others F1 | 8 | 60% | 53% |
| median extract time (float64, CPU) | 16 | 123 ms | 112 ms |

- **n** is the number of photos with a label for that attribute; blank labels are skipped. `fit`
  has no labels yet, so it has no row.
- **Scalars** (category, color, fabric) report accuracy: the top prediction equals the label.
- **`others`** reports precision (how many predicted features are real), recall (how many real
  features were found), and F1, summed over all features. Plain per-feature accuracy was dropped:
  most features are absent from most photos, so predicting "none" everywhere would score about 90%.
- **Latency** is one `extract()` call on an Apple-silicon laptop CPU in float64
  (`MODEL_DTYPE=float64`, needed on macOS 14.2). float32 should be roughly twice as fast.

### Data

- 20 photos downloaded from [Openverse](https://openverse.org) with licenses that allow reuse
  and modification (CC BY 2.0, CC BY-SA 2.0, CC0): 2 per search term for 10 jacket styles. Creator,
  license, and source URL for each photo are recorded alongside the images. **The photos are not
  committed to this repository.**
- 4 photos were excluded: one contains no jacket, one shows the jacket too small to judge, one
  shows two people in different jackets, and one is too blurry to label.
- The search term is not used as the label (e.g. the "blazer" results are leather jackets). Labels
  describe what is visible in each photo and were drafted by one person; **they have not yet been
  double-checked by a second team member.** Attributes that couldn't be judged were left blank.

### Observations

- FashionCLIP beats base CLIP on every scalar attribute and on `others` F1, supporting it as the
  primary model (plan §2).
- **Category is weakest (44%)**, below the 60% trigger in the risk register (plan §8). Most misses
  are overlapping vocabulary rather than wrong garments: generic `jacket` / `coat` labels against
  specific predictions such as `trench coat`, `trucker jacket`, or `parka`.
- **`others` over-predicts** (precision 50%). `double-breasted`, `quilted`, `embroidery`, and
  `patches` cause most of the false positives; graphic or painted jackets trigger the last two.
  Per-feature thresholds in `attributes.yaml` exist for tuning these.
- Color misses are mostly neighbouring shades (red/orange, tan/brown, white/cream). One busy street
  photo returned `multicolor` because of the background.

### Limitations and next steps

- 16 internet photos is far too few to tune on; tuning now would only fit these photos.
- Re-run on the team-owned labeled set (S1-11), then tune thresholds and the category vocabulary
  (S3-1).

### Reproduce

```bash
pip install -e ".[dev,ml]"
python scripts/zero_shot_accuracy.py <labels.csv> --out results.md
```

Labels CSV format: see the docstring at the top of `scripts/zero_shot_accuracy.py`.

## S2-3 / S2-4 / S2-5: edit-aware search (preliminary)

**Date:** Nov 8, 2026 · **Owner:** Member A · **Code:** `backend/app/ml/index.py`, `query.py`, `rerank.py`

Search over the 500-listing local index (`scripts/ingest.py` → `scripts/build_embeddings.py`),
FashionCLIP, float64 on a laptop CPU. Each query is an Openverse photo from the S1-5 set (none are
in the index) with one color edit, e.g. `puffer_02` blue → red.

| Metric | Without edit arithmetic (λ = 0) | With edit arithmetic (λ = 1) |
|---|---|---|
| Edit-satisfaction (share of the top 10 in the new color) | 61% | **80%** |

- 8 color edits; a result counts when the listing's dataset color label (mapped to our vocabulary,
  e.g. Grey → gray) includes the new color. λ = 0 still uses the edited caption in the text terms.
- λ = 2 reached 85% with an earlier calibration but moved the results further from the upload's
  look, so λ stays at the plan's 1.0 until S3-1 tuning.
- **Latency:** one search takes ~60 ms once the model and index are loaded. Building the index takes
  ~50 s for 500 listings and runs once.
- **Match score:** each similarity term is rescaled from 0 (typical unrelated listing) to 1 (closest
  match measured) before weighting, because image-to-image and text-to-image cosines sit on very
  different ranges. Anchors are in `CALIBRATION` in `rerank.py` and must be re-measured if the model
  or data changes.
- **Calibration overlaps the evaluation set:** the `CALIBRATION` anchors were measured on the same
  Openverse photos these 8 edits use, which flatters the 80% slightly. Re-measure the anchors on
  the team-owned S1-11 set and report edit-satisfaction on photos the anchors never saw (S3-1).
- Small sample (8 edits, color only). Feature edits (e.g. removing a hood) can't be scored yet: the
  dataset has no feature labels.
