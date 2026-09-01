---
name: glm-image-generation
description: Generate images with Z.AI GLM-Image (glm-image) via api.z.ai. Best-in-class text rendering — posters, PPT slides, infographics, multi-panel comics, diagrams with accurate embedded text. Use when the user asks for image generation with glm-image, GLM, Z.AI or ZhipuAI, or when a task needs a poster/slide/diagram image with precise text.
---

# GLM-Image Generation (Z.AI)

## Overview

GLM-Image — Z.AI / ZhipuAI text-to-image model ($0.015/image). Hybrid autoregressive + diffusion decoder; SOTA-level open-source text rendering. Sweet spots: commercial posters, popular-science diagrams, PPT-style layouts, multi-panel graphics, social-media covers.

Output is a **temporary URL (~30 days)** — the CLI downloads the file by default. `hd` quality (default) takes ~20-40s, `standard` ~5-10s.

## Quick Start

CLI (stdlib-only, single file at `scripts/glm-image.py`); install: `ln -s "$PWD/scripts/glm-image.py" ~/.local/bin/glm-image`. API key comes from env or an env file (default `~/agents.env`, any `KEY=value` lines):

```bash
glm-image "A cute kitten sitting on a sunny windowsill"                  # -> <slug>.png
glm-image "poster with big text SALE 50%" -o poster.png --ratio 16:9
glm-image "..." --size 1472x1088 --quality standard --url-only
```

Direct REST (same thing the CLI does):

```bash
curl -sS https://api.z.ai/api/paas/v4/images/generations \
  -H "Authorization: Bearer $ZAI_CODING_PLAN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"glm-image","prompt":"...","size":"1280x1280","quality":"hd"}'
# -> {"created":...,"data":[{"url":"https://mfile.z.ai/....png"}]}
```

Then download `data[0].url` (plain GET).

## Parameters

| CLI flag | API field | Notes |
|---|---|---|
| `--size WxH` | `size` | default `1280x1280`; recommended: `1568x1056`, `1056x1568`, `1472x1088`, `1088x1472`, `1728x960`, `960x1728`. Custom: 1024–2048 per side, **multiple of 32**, `w*h ≤ 2^22` |
| `--ratio` | `size` | `1:1 3:2 2:3 4:3 3:4 16:9 9:16` → maps to recommended enums |
| `--quality` | `quality` | `hd` (default, detailed) or `standard` (fast drafts) |
| `--model` | `model` | `glm-image` (default) |
| `--user-id` | `user_id` | optional, 6–128 chars |
| `-o/--out` | — | output path (default `<prompt-slug>.png`) |
| `--url-only`, `--json` | — | print URL / raw response without downloading |
| `--api-key`, `--env`, `--timeout` | — | key resolution; env file default `~/agents.env` |

## Key resolution

`--api-key` → env `GLM_IMAGE_API_KEY` → `ZAI_API_KEY` → `ZHIPUAI_API_KEY` → `ZAI_CODING_PLAN_API_KEY` → those same names looked up in `--env` file (default `~/agents.env`).

## Prompting Tips

- Text rendering is the killer feature: quote exact strings to render, describe layout zones (header / hero / footer), font style, palette. Works well for bilingual (EN/CN) text.
- Posters/PPT/diagrams: specify structure explicitly — panel order, labels, captions, arrows.
- Long prompts are fine; put the text content verbatim in quotes.

## Troubleshooting

- **Watermark** — images from coding-plan keys carry a Z.AI watermark (visible in the mfile.z.ai filename).
- **HTTP 429 / rate limit** — retry with backoff; hd generation is ~20-40s, don't lower the timeout below 60s.
- **`content_filter` in response** — prompt (or part of context) was flagged (`level 0` most severe); rephrase.
- **URL dead / 403 on download** — links expire after ~30 days; the CLI downloads immediately, so this only hits `--url-only` workflows.
- **`no API key`** — pass `--api-key`, export one of the env names, or add `ZAI_CODING_PLAN_API_KEY=...` to `~/agents.env`.
