# Decisions

Short record of team decisions (plan §9): date, decision, reason. Newest first.

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
  the query photos and for the top-10 results of every feature-edit search.
