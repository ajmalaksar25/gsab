# The Video Framework — a reusable system for short tech/product videos

A portable playbook for producing short videos that **hook, retain, and convert** — and
that crop safely to every platform. Project-agnostic: swap the *subject* (the app/feature),
the *brand tokens*, and the *script*; the structure, positioning, motion, sound, and
platform rules stay the same. Grounded in the GSAB realtime demo as the worked example.

---

## 1. The narrative spine (how to write the storyboard)

Two lenses, used together:

- **6-beat structure:** Hook · Setup · Journey · The Point · Audience · Close
- **AIDA:** Attention · Interest · Desire · Action

Rules of attention (non-negotiable):
- **Hook in the first 3 seconds** — cold-open on the *payoff/result*, never a slow title card.
- **Re-hook every ~3 seconds** — each beat must deliver a new visual payoff (a change, a
  reveal, a keyword) or you lose them.
- Optimize **value-per-second**; every beat earns the next. Target 20–35s for short-form.

**Storyboard table — fill one row per beat:**

| # | Time | AIDA | On-screen action | THE keyword | Caption | VO line | SFX | Camera |
|---|------|------|------------------|-------------|---------|---------|-----|--------|

The single most important column is **THE keyword** — the one word this beat is about.
Everything (motion, caption highlight, VO emphasis, sound) points at it.

Worked example (GSAB): `STORYBOARD.md` in this folder.

---

## 2. Eye-flow — how you guide the viewer's vision

You are directing attention, not decorating. The eye is pulled in this priority order:

1. **Motion** (strongest) → 2. **Faces** → 3. **High-contrast / saturated color** →
4. **Large text** → 5. everything else.

So **lead with motion**: the cursor moving, a push-in, a row flashing. Then let color
(the emerald highlight) and text land the meaning. Reinforce with **sound** — a cue pulls
the ear, which pulls the eye.

**Scanning patterns** — place the *next* element where the eye is already going:
- **Z-pattern** (sparse / landscape 16:9): top-left → top-right → diagonal → bottom-right.
  Brand top-area, action center, CTA/keyword bottom-center-right.
- **F-pattern** (text-heavy): left-aligned stacks. Avoid for video.
- **Center-out** (vertical 9:16): the eye locks center. Keep the subject and the keyword
  dead-center; let motion radiate out.

**One focal point per beat.** Stage every transition so the eye is *always* on the active
element — dim/blur the inactive area, or push the camera in on the live one. Never make the
viewer hunt.

---

## 3. Positioning & safe zones (the rule that makes it scale)

**The safe zone is centered. Corners are NOT safe.** Anything jammed in a corner (a) gets
cropped by platform UI, and (b) reads as an afterthought. Push key elements toward the
**centered safe zone** with generous padding from every edge.

**Design once, at the most-constrained crop (9:16), so it survives every platform:**

- **Universal safe zone** (visible on Reels + Shorts + TikTok + Stories): **center 900×1400**
  inside a 1080×1920 frame. Put *all* critical content — subject, the keyword, faces, logo,
  CTA — inside this box.
- **Vertical reserved bands:** top **~14% (250px)** = status bar / profile; bottom
  **~20–35% (340–670px)** = caption, audio, like/comment/share. Keep key content out of them.
- **Right column ~120px** = interaction buttons — never put text there.
- **Side edges ~6%** = decorative only (gradient, glow, motion graphics that may crop).
- **16:9:** title-safe = central **~90%** (≥5% / ~54px top-bottom, ~96px sides); action-safe ~93%.

**Element placement (applies to data, text, overlays — everything):**
- **Hero/subject** → dead center.
- **Primary caption / keyword** → lower-center, *above* the bottom reserved band (not the corner).
- **Brand / watermark** → top-center or top with real padding; small, low-priority.
- **CTA** → center.
- **Decoration only** (glow, grain, ledger lines, gradients) → the unsafe edges.

> Mental model: imagine the frame cropped to a tall phone with UI chrome top and bottom.
> If a thing you care about disappears, it's mis-placed.

---

## 4. Motion design

- **Continuous visual evolution — no hard cuts** (especially the first 10s). One unbroken
  take with evolving overlays beats frenetic editing.
- **Refined easing**, not linear: anticipation → action → follow-through. Use spring/quint
  curves (`power3`, `back.out`) — never default ease.
- **Camera with intent:** push *in* on detail (keeps the action legible), pull *back* for
  overview/value. The move is motivated by the story beat, not decoration.
- **Stage the frame:** the subject lives in a **framed product shot** (window chrome, depth,
  soft shadow) on a brand background — premium, and it crops well.
- Subtlety wins. If a motion doesn't guide attention, cut it.

---

## 5. Sound design (no music here, but the discipline is universal)

- **Sparse and clean.** "One well-placed sound beats five." Sound only on moments that matter.
- **Sync to action:** a soft **tap** on the interaction, a soft **confirm** when the result
  lands (the payoff), one low **impact** at the CTA. No whooshes, no noisy filler, no static.
- **VO is king** — keep it clear and forward; duck everything else under it. Pace fast but
  intelligible. Target ~ -14 LUFS, peaks ≤ -1 dBTP.
- Captions carry the message when muted (most feeds autoplay silent) — see §6.

---

## 6. Captions & keyword highlighting

- **Highlight the ONE word** that this beat is about (color box behind it). Don't highlight
  everything — then nothing stands out.
- Style: bold sans, key word in a solid brand-color box, occasional tilted tag for energy
  (the GSAP/Figma technique). Animate in (box wipes left→right, word lifts, tag pops).
- **Legibility:** heavy weight + a legibility scrim/gradient behind, sized to the caption.
  Assume muted autoplay — the video must read with sound off.
- Position lower-center within the safe zone (§3), never the bottom corner.

---

## 7. Brand system (swap per project)

Tokens travel as variables so the framework is reusable. For GSAB:
- Palette: paper `#f7f6f2`, ink `#17160f`, emerald `#1b7a4b`/`#23a25e`, amber `#eda52e`, clay `#cf6b3f`.
- Fonts: Fraunces (display), Hanken Grotesk (body), JetBrains Mono (code/labels).
- Texture: warm paper gradient, soft emerald glow, faint ledger ruling, 4% grain.

For a new project, replace the palette + fonts + texture; keep the structure.

---

## 8. Platform optimization matrix

| Platform | Ratio | Resolution | Duration sweet-spot | Safe zone | Notes |
|---|---|---|---|---|---|
| **YouTube (standard)** | 16:9 | 1920×1080 | 30–60s | central ~90% | The master. Landscape, Z-flow. |
| **YouTube Shorts** | 9:16 | 1080×1920 | 15–60s (≤3min) | ≥672px from bottom, ≥192px right | Subscribe button bottom-right. |
| **Instagram Reels** | 9:16 | 1080×1920 | <90s (15–30s ideal) | top 14% / bottom 20% clear; right ~120px | Caption+audio bottom. |
| **Facebook Reels** | 9:16 | 1080/1440×1920/2560 | 15–30s | top 14% / **bottom 35%** / sides 6% | Most aggressive bottom crop. |
| **Instagram feed** | 4:5 or 1:1 | 1080×1350 / 1080×1080 | ≤60s | central ~85% | Stops the scroll; less UI overlap. |

Encoding (all): **MP4 · H.264 high · yuv420p · AAC ≥128kbps · +faststart**. 1080p, 30fps
(60fps optional for Shorts). Keep files lean.

**Production strategy — one design, many crops:**
1. Build the master so every critical element sits in the **9:16 universal safe zone** even
   though you render 16:9 first. (Design center-safe → it crops to anything.)
2. Render the **16:9 master** (YouTube/web/site embed).
3. Reframe to **9:16** (Reels/Shorts/FB): subject centered, captions/CTA moved into the
   vertical safe band, brand top-center. (The parametric stage can render this natively.)
4. Optional **1:1 / 4:5** for feed.
Each export gets platform-correct duration, captions, and a cover/thumbnail.

> **Wide subjects don't crop — they re-layout.** A side-by-side / landscape subject
> center-zoomed in 9:16 lands on the seam and loses the action; fit-to-width makes it tiny.
> Instead **re-flow the subject for vertical** — e.g. stack the two panes (input on top,
> result below) so each is full-width and legible, and the vertical top→bottom scan *becomes*
> the story (edit up here → it updates down there). Make the subject itself responsive
> (a portrait breakpoint) so the same pipeline drives both. Overlays/safe-zones crop; the
> subject re-lays-out.

---

## 9. The production pipeline (reusable, parametric)

Three stages — all parametric on `{aspect, safeZone, brandTokens, beats}`:

1. **Stage** (`stage.html`): the *subject* (live app via iframe, or any media) inside a
   framed window on the brand background; overlay layer for cursor/selection, captions,
   brand, CTA. A `__stage` JS API drives every element.
2. **Director** (`director*.py`): a single **absolute-scheduled timeline** (drift-free) that
   fires, per beat: camera move, cursor/interaction, the real state change, caption. Records
   one continuous take (Playwright `recordVideo`).
3. **Assemble** (`assemble*.py`): trims the head, lays **VO at beat times + SFX at cue
   times**, mixes (VO forward, SFX ducked), exports per-platform MP4s.

To make a new video: write the storyboard (§1), drop the new subject into the stage, set the
brand tokens (§7), update the beat timeline + VO lines, render. To add a platform: change
`{aspect, safeZone}` and re-export.

---

## 10. Pre-flight checklist

- [ ] Payoff visible in the **first 3s**; a re-hook every ~3s.
- [ ] Every critical element inside the **centered safe zone** (test the 9:16 crop).
- [ ] **One focal point** per beat; the eye is led by motion → color → text.
- [ ] Captions readable **with sound off**; one keyword highlighted per beat.
- [ ] Sound only on moments that matter; VO clear and forward.
- [ ] Continuous motion, no hard cuts; camera moves are motivated.
- [ ] CTA centered; brand padded from the corner, not in it.
- [ ] Exported per platform (ratio · duration · safe zone · encoding).

---

### Sources
- Motion principles: Toptal motion design, Google Design "Making motion meaningful".
- Sound for demos: bluecarrot / Vidico SaaS demo best practices.
- Platform specs & safe zones (2026): Sprout Social, Kreatli safe-zone hub, Zeely, House of Marketers.
