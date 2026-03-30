# Khan Academy Video Text Re-Rendering

**Programmatic localization of on-screen text in Khan Academy blackboard-style videos.**

[**Live Demo →**](https://blueeyes08.github.io/Khan-Video-Text-ReRendering/)

---

## The problem

Khan Academy videos are dubbed into dozens of languages, but the English text Sal Khan writes on screen stays in English. Replacing it currently requires someone with a drawing tablet, handwriting patience, and about an hour per 5-minute video. For thousands of videos across 40+ languages, that's an impossible backlog.

## The idea

What if we could detect the text programmatically, translate it, and re-render it — at the same position, angle, and timing as the original — using AI and code instead of humans and tablets?

## How it works

The pipeline has three phases:

**Phase 1: Backwards frame scanning.** We walk through the video frames in reverse. This is the key insight — seeing *complete* text first means OCR is reliable (no trying to read half-written words). We log when each text region disappears, stabilizes, and first appears.

**Phase 2: Translation.** The detected English text is translated. This can use any translation API, or the [Translation Triangulation](https://olofpaulson.substack.com/) method (using existing approved translations in other languages as disambiguation context).

**Phase 3: Overlay rendering.** A black patch covers each original English text region (diagonal reveal from top-left to bottom-right), and the translated text is written in with a handwriting-style animation — matching the original angle, position, and timing.

Combined with AI audio dubbing (ElevenLabs, CAMB.AI, Fish Speech, etc.), this could reduce per-video localization from ~1 hour to ~15 minutes of human review.

## What's here

| File | What it does |
|------|-------------|
| `index.html` | Interactive concept demo (runs in browser, no dependencies) |
| `khan_localize_poc.py` | Python pipeline: backwards scan → OCR → translate → overlay |
| `KhanLocalizedVideo.tsx` | Remotion (React) component for production-quality rendering |

## Quick start

### Browser demo
Open `index.html` or visit the [live demo](https://blueeyes08.github.io/Khan-Video-Text-ReRendering/). No install needed.

### Python pipeline
```bash
pip install opencv-python-headless pytesseract Pillow numpy
sudo apt install tesseract-ocr

# Scan and localize a video
python khan_localize_poc.py input.mp4 --lang sv --output output_sv.mp4

# Just scan and export data for Remotion
python khan_localize_poc.py input.mp4 --scan-only --export-json regions.json
```

### Remotion (higher quality)
```bash
npx create-video@latest my-khan-project
cd my-khan-project
npx skills add remotion-dev/skills

# Use the exported regions.json + KhanLocalizedVideo.tsx
npx remotion studio
```

## Status

This is a proof of concept, not production software. The demo is a simulation — no actual video processing happens in the browser. The Python script and Remotion component are functional but need testing against real Khan videos.

**What works:** text detection on high-contrast blackboard video, basic overlay rendering, angle-aware text placement, handwriting-style progressive reveal.

**What needs work:** mathematical notation (fractions, exponents), diagram/drawing detection, font matching, timing fine-tuning, integration with audio dubbing pipeline.

## The bigger picture

AI dubbing costs have dropped to $1-20/minute. Voice synthesis preserves speaker identity across languages. OCR and programmatic video rendering can handle the visual layer. Translation quality is converging on human-level for many language pairs.

The localization bottleneck is no longer technical. Global translation teams can transition from manually remaking content to validating and distributing AI-generated localizations.

## Contributing

This is an open invitation to the Khan Academy translation community. If you work on Khan localization in any language and want to help test, improve, or extend this:

- Try the demo and tell us what's missing
- Test the Python script on a real Khan video and share results
- Suggest better approaches to any part of the pipeline
- Help build the translation layer for your language

Open an issue or reach out.

## Credits

Built by [Olof Paulson](https://github.com/blueeyes08) — Khan Academy translation advocate since 2011,  Python course creator on Scrimba, and enthusiastic believer that localization at scale is now possible.

## License

MIT
