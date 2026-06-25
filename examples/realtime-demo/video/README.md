# GSAB realtime demo — launch video

A short (~30s) launch video proving GSAB's reactive `watch()` is **real**, not a mockup.
The middle of the video is the *actual* side-by-side demo app captured live: a person
edits the real Google Sheet on the left, and the GSAB-powered app on the right updates
~1s later. The intro/outro cards use the site's exact design system (Fraunces · Hanken
Grotesk · JetBrains Mono, warm-paper/emerald tokens, grain) so it reads as an extension
of gsab.ajmalaksar.com.

## Deliverables

| File | What |
|------|------|
| `gsab-realtime-demo.mp4` | Final cut — 1920×1080, 30fps, H.264, ~30s, silent. |
| `gsab-realtime-thumbnail.png` | Thumbnail, 1920×1080. |
| `gsab-realtime-thumbnail-1280.png` | Thumbnail, 1280×720 (standard). |
| `VO-script.md` | ~30s voiceover script, time-aligned to the cut (optional VO). |
| `build/` | Reproducible sources: bookend HTML, the recorder, thumbnail composer. |

The live middle segment is genuinely the running system: a clean (anonymous) headless
Chromium loads the demo page — which embeds the **real, publicly-shared Google Sheet** on
the left and the GSAB `watch()`-over-SSE table on the right — while a worker thread makes
real edits through a separate GSAB connection. Both panes update live (Google pushes the
sheet change to the view-only iframe; GSAB pushes the same change to the app via SSE).

## How it's built (reproducible)

Needs `playwright` (+ chromium) and `imageio-ffmpeg` in the env. From the repo root:

```bash
# 1. Run the demo app (creates + shares + seeds a real sheet, prints its id)
python examples/realtime-demo/server.py        # serves http://127.0.0.1:8137

# 2. Record the choreographed live segment (worker thread fires timed edits).
#    Pass the sheet id printed by the server.
python examples/realtime-demo/video/build/record_demo.py <SHEET_ID> ./out 1920 1080

# 3. Record the two bookend cards
python examples/realtime-demo/video/build/record_card.py build/intro.html ./out_intro 5500
python examples/realtime-demo/video/build/record_card.py build/outro.html ./out_outro 6500

# 4. Trim + crossfade-assemble (see build/assemble.ps1 for the exact ffmpeg commands)

# 5. Thumbnail: grab a side-by-side frame, then compose
python examples/realtime-demo/video/build/shot_thumb.py build/thumbnail.html hero_frame.png thumbnail.png
```

`build/assemble.ps1` has the exact trim + `xfade` ffmpeg invocations used for v1.

## Embedding on gsab-frontend

Drop the mp4 + thumbnail into `gsab-frontend/public/` and embed:

```html
<video
  src="/realtime/gsab-realtime-demo.mp4"
  poster="/realtime/gsab-realtime-thumbnail.png"
  controls playsinline preload="metadata"
  style="width:100%;border-radius:14px;border:1px solid var(--line)">
</video>
```

## Positioning (keep honest)

Experimental · **polling (~1s), not push** — Google Sheets has no change stream. Great
for dashboards, internal tools, config and small-team collaboration; not for
high-frequency writes, strict transactions, or huge/hot tables. A Convex-*feel* for that
envelope, not a database replacement.
