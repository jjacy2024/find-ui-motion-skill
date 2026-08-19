# Visual Retrieval

Use this workflow after concrete candidates have real task-scoped clips or ordered keyframes. Keep model weights, captures, and generated indexes outside the Skill folder.

## Runtime contract

- Require NumPy, OpenCV, Pillow, PyTorch, and `open_clip_torch` for the full path.
- Never install packages or download a checkpoint without user authorization. When authorized, install with `python3 -m pip install open_clip_torch torch pillow`; add `opencv-python-headless` only when OpenCV is missing.
- Cache model weights under `~/.codex/cache/find-ui-motion/models/openclip` by default.
- Default to OpenCLIP `ViT-B-32` with checkpoint `laion2b_s34b_b79k`. Verify its current model card before redistribution or production use; the library license and checkpoint license are separate.
- Translate a non-English query into one concise English visual description for `--semantic-query`; preserve the original query for metadata recall.

## Build a task-scoped index

Create a JSON capture manifest that points to real transient media:

```json
{
  "cases": [
    {
      "id": "catalog-example-id",
      "media": ["/absolute/rest.png", "/absolute/peak.png", "/absolute/settled.png"],
      "captured_at": "2026-08-19T12:00:00Z"
    }
  ]
}
```

Use an existing `examples.jsonl` ID. Do not add third-party captures to the Skill. Build the derived index into task output or the external cache:

```bash
python3 scripts/build_visual_index.py <capture-manifest.json> \
  --index <task-output/index.npz> \
  --metadata <task-output/metadata.json>
```

The builder selects event and SSIM-diverse keyframes, prefers DIS optical flow with Farneback fallback, extracts a shared dynamic-region crop, computes OpenCLIP vectors, and stores only `float16` embeddings, hashes, and compact motion signatures.

## Search and fuse

```bash
python3 scripts/search_visual_index.py "<original user query>" \
  --semantic-query "<concise English visual description>" \
  --intent '<compact motion-signature JSON>' \
  --index <index.npz> \
  --metadata <metadata.json> \
  --limit 8
```

Add `--reference-media <clip-or-frames>` when the user supplies a real reference. For text-only queries, compare only explicitly inferred categorical motion fields; never claim trajectory matching without a reference sequence.

Fuse metadata, full-frame OpenCLIP, dynamic-region OpenCLIP, and motion-signature ranks with RRF. Treat RRF and cosine values as relative ordering aids, never match probabilities.

## Selective VLM review

Read the returned `vlm_review` object:

- When `required=false`, stop before VLM analysis and return the fused links after source availability checks.
- When `required=true`, announce the purpose and real candidate count, then inspect only `candidate_ids`, at most five.
- Reuse the captured keyframes. Prefer one labeled four-frame contact sheet and a fixed compact motion-signature output over many independent image inputs.
- Respect `--vlm-policy never` when the user requests no deep review and `always` only when the user explicitly requests direct VLM inspection.
- Treat routing thresholds as heuristics until evaluated on labeled UI-motion queries.

## Degrade explicitly

If OpenCLIP is unavailable, retain metadata and motion-signature ranking and report `status=degraded`; do not call it OpenCLIP matching. If there is no real media, keep the result metadata-only. If a cached source hash or visible source state changed, recapture and rebuild only that case.
