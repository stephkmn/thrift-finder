# Decisions

Short record of team decisions (plan §9): date, decision, reason. Newest first.

## 2026-11-14 — S3-1 tuning: keep λ and weights; fit defaults to "regular fit"

**Decision.**

- Keep the edit strength λ = 1 and re-ranker weights (0.5, 0.3, 0.2) from plan §4.3.
- Fit reports a value other than "regular fit" only at ≥ 0.99 confidence (`default` and
  `min_confidence` in `backend/app/ml/attributes.yaml`), and fit is listed as a limitation.
- Evaluation scores our colors the dataset doesn't label by family (navy → Blue, olive → Green,
  cream → White or Beige, burgundy → Red).
- The results call the automatic metric "label-based P@10", not P@10: the plan's P@10 is
  team-judged, and the team labels only the query photos.

**Reasons.**

- On the S1-11 set, the best swept setting (λ = 1.5, weights (0.3, 0.4, 0.3)) beat the current one
  by 4 points of label-based P@10 (63% vs. 59%). With 27 scored edits, one query moves that by ~4
  points, so the gap is about one query; switching would fit these photos rather than the task.
  Those weights lead at every λ, so they are the first to re-test on a larger set.
- Zero-shot can't read fit: "regular" isn't a visual cue, so plain argmax rarely picks it (22% on the
  queries), and no threshold makes its other calls reliable (at most ~1 in 3 right on the train
  listings). Always answering "regular fit" scores 97% on the 461 labeled train listings and 84% on
  the queries. The 0.99 threshold, chosen on the **train** listings, scores 96% there and 84% on the
  queries (the same as always answering "regular fit"), while still allowing the rare confident
  call. An earlier 0.9 threshold scored below that baseline (85% train, 75% queries).
- The dataset has no navy, olive, cream, or burgundy labels, so without families an edit to navy
  scored 0 even when all ten results were navy jackets labeled "Blue".

Details: [`EVALUATION.md` → S3-1 / S3-2 / S3-3](EVALUATION.md#s3-1--s3-2--s3-3-results-on-the-s1-11-set).

## 2026-11-10 — S1-11 evaluation set: dataset test split + Member D's own photos

**Decision.** The S1-11 query set is a hybrid of 38 queries instead of 15–20 team-taken photos:

- **30 photos from the `test` split** of the licensed fallback dataset
  ([fnauman/fashion-second-hand-front-only-rgb](https://huggingface.co/datasets/fnauman/fashion-second-hand-front-only-rgb),
  CC BY 4.0), drawn at random with a fixed seed, stratified by garment type.
- **8 photos of Member D's own jackets** (4 jackets × 2 shots: laid flat, and worn or hung).

Member D owns the set and labels it. Details: [`EVALUATION.md` → S1-11 evaluation set](EVALUATION.md#s1-11-evaluation-set-hybrid).

**Reasons.**

- The search index is built only from the dataset's `train` split, so `test` photos can never appear
  among the listings. This keeps queries and search corpus separate, as `DATA.md` requires.
- The dataset already labels color, material, garment type, and cut, so most attribute labels come with
  the photos instead of being hand-drawn, and the set can be rebuilt by anyone from row indices.
- The plan already allows licensed dataset images for evaluation (§4.4 "images we have rights to";
  risk register: "licensed dataset images").
- The 8 own photos cover what the dataset can't: real phone photos (EXIF rotation, backgrounds, a jacket
  being worn), feature edits on real hooded jackets, and the three `samples/` images.
- S1-11 was overdue; this unblocks S3-1 tuning and the progress report's results.

**Trade-offs.**

- Dataset photos are second-hand inventory shots, which likely flatter results compared with photos of
  a jacket someone saw. The 8 own photos are reported separately to show the gap.
- The dataset has no labels for `others` features (hood, zipper, ...). Member D labels them by hand for
  the 38 query photos only, so feature edits (e.g. "remove hood") can't be scored automatically: the
  search results carry no feature labels. They are shown as screenshot examples and listed as a
  limitation.
