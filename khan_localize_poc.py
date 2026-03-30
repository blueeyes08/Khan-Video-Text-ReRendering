#!/usr/bin/env python3
"""
Khan Academy Video Localization POC
====================================
Detects on-screen text in Khan-style blackboard videos by scanning
frames backwards, then overlays translated text with handwriting-style
reveal animation.

Requirements:
    pip install opencv-python-headless pytesseract Pillow numpy

System dependency:
    sudo apt install tesseract-ocr

Usage:
    python khan_localize_poc.py input_video.mp4 --lang sv --output localized.mp4

Author: Built as POC for Khan Academy translation community
"""

import cv2
import numpy as np
import argparse
import json
import sys
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from PIL import Image, ImageDraw, ImageFont


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class TextRegion:
    """A detected text region with temporal bounds."""
    text: str                    # OCR'd English text
    translated: str = ""         # Translated text
    x: int = 0                   # Bounding box left
    y: int = 0                   # Bounding box top
    w: int = 0                   # Bounding box width
    h: int = 0                   # Bounding box height
    frame_first: int = 0         # First frame where text pixels appear
    frame_stable: int = 0        # Frame where text is fully written
    frame_last: int = 0          # Last frame where text is visible
    confidence: float = 0.0      # OCR confidence


# =============================================================================
# Phase 1: Backwards frame scanning + OCR
# =============================================================================

def scan_video_backwards(video_path: str, sample_rate: int = 5) -> list[TextRegion]:
    """
    Scan video frames in reverse order to detect text regions.
    
    The backwards approach means we see complete text first (easy to OCR),
    then walk back to find when it started appearing.
    
    Args:
        video_path: Path to input video
        sample_rate: Check every Nth frame (higher = faster but less precise)
    
    Returns:
        List of TextRegion objects with temporal bounds
    """
    try:
        import pytesseract
    except ImportError:
        print("ERROR: pytesseract not installed. Run: pip install pytesseract")
        print("Also need: sudo apt install tesseract-ocr")
        sys.exit(1)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {video_path}")
        sys.exit(1)
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video: {total_frames} frames, {fps:.1f} fps, {width}x{height}")
    print(f"Duration: {total_frames / fps:.1f}s")
    print(f"Scanning backwards (sample every {sample_rate} frames)...")
    
    # Collect all frames we need (reading forward, processing backward)
    frames_to_check = list(range(total_frames - 1, -1, -sample_rate))
    
    detected_regions: list[TextRegion] = []
    active_texts: dict[str, dict] = {}  # text -> tracking info
    
    prev_frame_gray = None
    
    for i, frame_idx in enumerate(frames_to_check):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue
        
        if i % 20 == 0:
            pct = (i / len(frames_to_check)) * 100
            print(f"  Scanning... {pct:.0f}% (frame {frame_idx}/{total_frames})")
        
        # Convert to grayscale and threshold for Khan-style white/colored text on dark bg
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Adaptive threshold works well for Khan's blackboard style
        # Text is bright on dark background
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        
        # OCR on the thresholded image
        ocr_data = pytesseract.image_to_data(
            thresh, output_type=pytesseract.Output.DICT,
            config='--psm 11'  # sparse text mode - good for scattered blackboard text
        )
        
        # Process OCR results
        current_texts = set()
        for j in range(len(ocr_data['text'])):
            text = ocr_data['text'][j].strip()
            conf = int(ocr_data['conf'][j])
            
            if len(text) < 2 or conf < 40:
                continue
            
            current_texts.add(text)
            
            if text not in active_texts:
                # First time seeing this text (but we're going backwards,
                # so this is actually the LAST frame it appears)
                active_texts[text] = {
                    'text': text,
                    'x': ocr_data['left'][j],
                    'y': ocr_data['top'][j],
                    'w': ocr_data['width'][j],
                    'h': ocr_data['height'][j],
                    'frame_last': frame_idx,   # we see it here going backward
                    'frame_stable': frame_idx,  # will update as we keep going back
                    'frame_first': frame_idx,   # will update as we keep going back
                    'confidence': conf,
                    'missing_count': 0
                }
            else:
                # Still visible - update first-seen frame
                active_texts[text]['frame_first'] = frame_idx
                active_texts[text]['missing_count'] = 0
        
        # Check for texts that have disappeared (going backwards = they haven't appeared yet)
        for text in list(active_texts.keys()):
            if text not in current_texts:
                active_texts[text]['missing_count'] += 1
                # After missing for several consecutive samples, finalize this region
                if active_texts[text]['missing_count'] > 3:
                    info = active_texts.pop(text)
                    region = TextRegion(
                        text=info['text'],
                        x=info['x'], y=info['y'],
                        w=info['w'], h=info['h'],
                        frame_first=info['frame_first'],
                        frame_stable=info['frame_last'],  # approx
                        frame_last=info['frame_last'],
                        confidence=info['confidence']
                    )
                    detected_regions.append(region)
                    t_start = region.frame_first / fps
                    t_end = region.frame_last / fps
                    print(f"  Found: \"{region.text}\" "
                          f"({t_start:.1f}s - {t_end:.1f}s, conf={region.confidence})")
    
    # Finalize any remaining active texts
    for text, info in active_texts.items():
        region = TextRegion(
            text=info['text'],
            x=info['x'], y=info['y'],
            w=info['w'], h=info['h'],
            frame_first=info['frame_first'],
            frame_stable=info['frame_last'],
            frame_last=info['frame_last'],
            confidence=info['confidence']
        )
        detected_regions.append(region)
    
    cap.release()
    
    # Sort by appearance time
    detected_regions.sort(key=lambda r: r.frame_first)
    
    print(f"\nDetected {len(detected_regions)} text regions.")
    return detected_regions


# =============================================================================
# Phase 2: Translation (stub - replace with real translation API)
# =============================================================================

# Simple translation lookup for POC demo
TRANSLATIONS = {
    'sv': {
        'King Louis XIV': 'Kung Ludvig XIV',
        'France': 'Frankrike',
        'Absolute Monarchy': 'Envalde',
        'Palace of Versailles': 'Slottet i Versailles',
        'Revolution': 'Revolution',
        'Taxes': 'Skatter',
        'Nobles': 'Adeln',
        'Third Estate': 'Tredje standet',
        # Add more as needed for your specific video
    }
}


def translate_regions(regions: list[TextRegion], target_lang: str) -> list[TextRegion]:
    """
    Translate detected text regions.
    
    In production, this would call a translation API or use your
    Translation Triangulation method. For POC, uses lookup table.
    """
    lookup = TRANSLATIONS.get(target_lang, {})
    
    for region in regions:
        # Try exact match first
        if region.text in lookup:
            region.translated = lookup[region.text]
        else:
            # Try case-insensitive partial match
            for eng, trans in lookup.items():
                if eng.lower() in region.text.lower() or region.text.lower() in eng.lower():
                    region.translated = trans
                    break
            else:
                # Fallback: mark as untranslated
                region.translated = f"[{region.text}]"
                print(f"  WARNING: No translation for \"{region.text}\"")
        
        print(f"  \"{region.text}\" -> \"{region.translated}\"")
    
    return regions


# =============================================================================
# Phase 3: Overlay rendering
# =============================================================================

def render_handwriting_frame(frame: np.ndarray, region: TextRegion,
                              progress: float, font_path: Optional[str] = None) -> np.ndarray:
    """
    Render translated text with handwriting-style progressive reveal.
    
    Args:
        frame: Video frame (BGR numpy array)
        region: Text region with translation
        progress: 0.0 = nothing visible, 1.0 = fully written
        font_path: Optional path to a handwriting TTF font
    
    Returns:
        Modified frame
    """
    if progress <= 0:
        return frame
    
    text = region.translated
    if not text:
        return frame
    
    # Expand the overlay region slightly
    margin = 8
    ox = max(0, region.x - margin)
    oy = max(0, region.y - margin)
    ow = region.w + margin * 2
    oh = region.h + margin * 2
    
    # Step 1: Black overlay to hide original text
    overlay_progress = min(progress * 2, 1.0)  # overlay appears in first half
    if overlay_progress > 0:
        overlay_width = int(ow * overlay_progress)
        frame[oy:oy+oh, ox:ox+overlay_width] = [26, 26, 26]  # dark blackboard color
    
    # Step 2: Draw translated text progressively
    if progress > 0.3:
        text_progress = (progress - 0.3) / 0.7
        chars_to_show = max(1, int(len(text) * text_progress))
        visible_text = text[:chars_to_show]
        
        # Use PIL for better text rendering
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        font_size = max(region.h - 4, 16)
        try:
            if font_path and os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
            else:
                # Try system fonts that look handwritten
                for fname in ['/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
                              '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf']:
                    if os.path.exists(fname):
                        font = ImageFont.truetype(fname, font_size)
                        break
                else:
                    font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        
        # Add slight per-character jitter for handwriting feel
        x_pos = region.x
        for ch in visible_text:
            jx = np.random.randint(-1, 2)
            jy = np.random.randint(-1, 2)
            draw.text((x_pos + jx, region.y + jy), ch, fill=(255, 255, 255), font=font)
            if hasattr(font, 'getbbox'):
                bbox = font.getbbox(ch)
                x_pos += bbox[2] - bbox[0]
            else:
                x_pos += font_size // 2
        
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    
    return frame


def overlay_video(input_path: str, output_path: str, regions: list[TextRegion]):
    """
    Create output video with translated text overlays.
    """
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    print(f"\nRendering output video: {output_path}")
    print(f"  {len(regions)} text regions to overlay")
    
    for frame_idx in range(total_frames):
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % int(fps * 5) == 0:
            print(f"  Rendering... {frame_idx}/{total_frames} "
                  f"({frame_idx/total_frames*100:.0f}%)")
        
        # Apply overlays for each active region
        for region in regions:
            if frame_idx < region.frame_first or frame_idx > region.frame_last:
                continue
            
            # Calculate animation progress
            write_duration = max(1, region.frame_stable - region.frame_first)
            if frame_idx <= region.frame_stable:
                # Text is being "written"
                progress = (frame_idx - region.frame_first) / write_duration
            else:
                # Text is fully visible
                progress = 1.0
            
            frame = render_handwriting_frame(frame, region, progress)
        
        out.write(frame)
    
    cap.release()
    out.release()
    print(f"  Done! Output: {output_path}")


# =============================================================================
# Phase 4: Export detection data (for Remotion pipeline)
# =============================================================================

def export_for_remotion(regions: list[TextRegion], fps: float, output_path: str):
    """
    Export detected regions as JSON for use in a Remotion project.
    This enables the React/TypeScript pipeline for higher quality output.
    """
    data = {
        'fps': fps,
        'regions': []
    }
    for r in regions:
        data['regions'].append({
            'originalText': r.text,
            'translatedText': r.translated,
            'x': r.x, 'y': r.y, 'w': r.w, 'h': r.h,
            'startTime': r.frame_first / fps,
            'stableTime': r.frame_stable / fps,
            'endTime': r.frame_last / fps,
            'confidence': r.confidence
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\nExported Remotion data to: {output_path}")
    print(f"  Use this JSON in your Remotion <TextOverlay> component")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Khan Academy Video Localization POC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan and localize a video to Swedish
  python khan_localize_poc.py khan_louis_xiv.mp4 --lang sv
  
  # Just scan and export detection data for Remotion
  python khan_localize_poc.py khan_video.mp4 --scan-only --export-json regions.json
  
  # Use a custom handwriting font
  python khan_localize_poc.py khan_video.mp4 --lang sv --font ./Caveat-Regular.ttf
        """
    )
    parser.add_argument('input', help='Input video file')
    parser.add_argument('--lang', default='sv', help='Target language code (default: sv)')
    parser.add_argument('--output', default=None, help='Output video path')
    parser.add_argument('--sample-rate', type=int, default=5,
                        help='Check every Nth frame (default: 5)')
    parser.add_argument('--scan-only', action='store_true',
                        help='Only scan, don\'t render output video')
    parser.add_argument('--export-json', default=None,
                        help='Export region data as JSON (for Remotion)')
    parser.add_argument('--font', default=None,
                        help='Path to TTF font for handwriting style')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)
    
    # Phase 1: Detect text
    print("=" * 60)
    print("PHASE 1: Backwards frame scan + OCR")
    print("=" * 60)
    regions = scan_video_backwards(args.input, args.sample_rate)
    
    if not regions:
        print("No text regions detected. Try adjusting --sample-rate.")
        sys.exit(0)
    
    # Phase 2: Translate
    print("\n" + "=" * 60)
    print(f"PHASE 2: Translation (target: {args.lang})")
    print("=" * 60)
    regions = translate_regions(regions, args.lang)
    
    # Phase 3: Export JSON if requested
    if args.export_json:
        cap = cv2.VideoCapture(args.input)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        export_for_remotion(regions, fps, args.export_json)
    
    # Phase 4: Render output video
    if not args.scan_only:
        output_path = args.output or args.input.replace('.mp4', f'_{args.lang}.mp4')
        print("\n" + "=" * 60)
        print("PHASE 3: Rendering localized video")
        print("=" * 60)
        overlay_video(args.input, output_path, regions)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in regions:
        print(f"  [{r.frame_first:5d}-{r.frame_last:5d}] "
              f"\"{r.text}\" -> \"{r.translated}\"")
    print(f"\nTotal regions: {len(regions)}")


if __name__ == '__main__':
    main()
