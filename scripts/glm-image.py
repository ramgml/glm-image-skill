#!/usr/bin/env python3
"""glm-image — text-to-image via Z.AI GLM-Image (https://docs.z.ai/guides/image/glm-image).

Stdlib-only. The API returns a temporary URL (valid ~30 days); by default the
CLI downloads the image. Key resolution: --api-key, then env GLM_IMAGE_API_KEY /
ZAI_API_KEY / ZHIPUAI_API_KEY / ZAI_CODING_PLAN_API_KEY, then --env file
(default ~/agents.env).
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.z.ai/api/paas/v4/images/generations"
ENV_NAMES = ("GLM_IMAGE_API_KEY", "ZAI_API_KEY", "ZHIPUAI_API_KEY", "ZAI_CODING_PLAN_API_KEY")
RATIOS = {
    "1:1": "1280x1280",
    "3:2": "1568x1056",
    "2:3": "1056x1568",
    "4:3": "1472x1088",
    "3:4": "1088x1472",
    "16:9": "1728x960",
    "9:16": "960x1728",
}


def fail(msg: str, code: int = 1):
    print(f"glm-image: {msg}", file=sys.stderr)
    sys.exit(code)


def load_env_file(path: str) -> dict:
    env = {}
    p = Path(path).expanduser()
    if not p.is_file():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip().strip('"').strip("'")
        if val:
            env[key.strip()] = val
    return env


def resolve_key(args) -> str:
    if args.api_key:
        return args.api_key
    for name in ENV_NAMES:
        val = os.environ.get(name)
        if val:
            return val
    env = load_env_file(args.env)
    for name in ENV_NAMES:
        if env.get(name):
            return env[name]
    fail(f"no API key: pass --api-key, export one of {', '.join(ENV_NAMES)}, or keep it in {args.env}")


def parse_size(size: str) -> str:
    m = re.fullmatch(r"(\d{3,4})x(\d{3,4})", size)
    if not m:
        fail(f"bad --size {size!r}: expected WxH, e.g. 1280x1280")
    w, h = int(m[1]), int(m[2])
    if not (1024 <= w <= 2048 and 1024 <= h <= 2048):
        fail(f"size {size}: width and height must be within 1024-2048")
    if w % 32 or h % 32:
        fail(f"size {size}: width and height must be multiples of 32")
    if w * h > 2 ** 22:
        fail(f"size {size}: w*h must not exceed 2^22 px")
    return size


def slugify(prompt: str, limit: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:limit].strip("-")
    return slug or "image"


def post_json(req: urllib.request.Request, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            body = json.loads(body).get("message") or body
        except Exception:
            pass
        fail(f"HTTP {e.code}: {body.strip()[:500]}")
    except urllib.error.URLError as e:
        fail(f"network error: {e.reason}")


def download(url: str, dest: str, timeout: int, attempts: int = 4):
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "glm-image-cli/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
                while chunk := resp.read(1 << 16):
                    f.write(chunk)
            return
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 403 and e.code != 404:
                fail(f"download failed: HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError) as e:
            reason = getattr(e, "reason", e)
            if i == attempts - 1:
                fail(f"download failed: {reason}")
        time.sleep(3 * (i + 1))
    fail("download failed after retries")


def main():
    ap = argparse.ArgumentParser(
        prog="glm-image", description="Generate an image via Z.AI GLM-Image (api.z.ai)."
    )
    ap.add_argument("prompt", nargs="+", help="text prompt (multi-word, quotes optional)")
    ap.add_argument("-o", "--out", help="output .png path (default: <prompt-slug>.png)")
    ap.add_argument("--size", help="WxH; 1024-2048 per side, multiple of 32 (default 1280x1280)")
    ap.add_argument("--ratio", choices=sorted(RATIOS), help="aspect ratio -> recommended size enum")
    ap.add_argument("--quality", choices=("hd", "standard"), default="hd",
                    help="hd: detailed, ~20-40s (default); standard: fast, ~5-10s")
    ap.add_argument("--model", default="glm-image", help="model code (default glm-image)")
    ap.add_argument("--url-only", action="store_true", help="print the temporary URL, don't download")
    ap.add_argument("--json", action="store_true", help="print raw API JSON response")
    ap.add_argument("--api-key", help="API key (else env vars, else --env file)")
    ap.add_argument("--env", default="~/agents.env", help="env file with KEY=VALUE lines")
    ap.add_argument("--user-id", help="optional end-user id, 6-128 chars")
    ap.add_argument("--timeout", type=int, default=300, help="API request timeout, seconds (default 300)")
    args = ap.parse_args()
    prompt = " ".join(args.prompt)

    if args.size and args.ratio:
        fail("use --size or --ratio, not both")
    if args.size:
        size = parse_size(args.size)
    elif args.ratio:
        size = RATIOS[args.ratio]
    else:
        size = "1280x1280"

    payload = {"model": args.model, "prompt": prompt, "size": size, "quality": args.quality}
    if args.user_id:
        payload["user_id"] = args.user_id

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {resolve_key(args)}",
            "Content-Type": "application/json",
        },
    )
    t0 = time.time()
    resp = post_json(req, args.timeout)
    if args.json:
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    url = (resp.get("data") or [{}])[0].get("url")
    if not url:
        fail(f"no image URL in response: {json.dumps(resp)[:300]}")
    for item in resp.get("content_filter") or []:
        if isinstance(item, dict) and item.get("level", 3) <= 1:
            print(f"warning: content_filter level={item.get('level')} role={item.get('role')}",
                  file=sys.stderr)

    if args.url_only:
        print(url)
        return

    ext = ".png"
    out = args.out or f"{slugify(prompt)}{ext}"
    download(url, out, timeout=max(args.timeout, 120))
    magic = open(out, "rb").read(4)
    kind = "PNG" if magic.startswith(b"\x89PNG") else "JPEG" if magic.startswith(b"\xff\xd8") else "unknown"
    if not args.out and kind != "unknown" and out.endswith(ext):
        real_ext = ".png" if kind == "PNG" else ".jpg"
        if real_ext != ext:
            os.rename(out, new_out := f"{slugify(prompt)}{real_ext}")
            out = new_out
    size_bytes = Path(out).stat().st_size
    print(f"saved {out} ({size_bytes} bytes, {kind}, {size}, {time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
