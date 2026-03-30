/**
 * Khan Academy Video Localization - Remotion Component
 * =====================================================
 * 
 * This component overlays translated text on a Khan Academy video,
 * using the region data exported by khan_localize_poc.py
 * 
 * Usage in your Remotion project:
 *   1. Run the Python scanner: python khan_localize_poc.py video.mp4 --export-json regions.json
 *   2. Place video.mp4 in public/
 *   3. Place regions.json in src/data/
 *   4. Import and use this component
 * 
 * Setup:
 *   npx create-video@latest
 *   npx skills add remotion-dev/skills
 *   npm install @remotion/paths  (for SVG handwriting animation)
 */

import React from 'react';
import {
  AbsoluteFill,
  Video,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
} from 'remotion';

// =============================================================================
// Types
// =============================================================================

interface TextRegion {
  originalText: string;
  translatedText: string;
  x: number;
  y: number;
  w: number;
  h: number;
  startTime: number;   // seconds - first pixel appears
  stableTime: number;  // seconds - text fully written
  endTime: number;     // seconds - text leaves frame
  confidence: number;
}

interface RegionsData {
  fps: number;
  regions: TextRegion[];
}

interface KhanLocalizedVideoProps {
  videoSrc: string;        // path to original video in public/
  regionsData: RegionsData; // imported from JSON
  videoWidth: number;       // original video width (for coordinate scaling)
  videoHeight: number;      // original video height
}

// =============================================================================
// Handwriting reveal component
// =============================================================================

const HandwritingText: React.FC<{
  text: string;
  x: number;
  y: number;
  w: number;
  h: number;
  progress: number; // 0 to 1
  fontSize: number;
}> = ({ text, x, y, w, h, progress, fontSize }) => {
  const charsToShow = Math.ceil(text.length * Math.min(progress, 1));
  const visibleText = text.substring(0, charsToShow);
  
  // Black overlay to hide original text
  const overlayProgress = Math.min(progress * 1.5, 1);
  
  return (
    <>
      {/* Black overlay to cover original English text */}
      <div
        style={{
          position: 'absolute',
          left: x - 6,
          top: y - 4,
          width: (w + 12) * overlayProgress,
          height: h + 8,
          backgroundColor: '#1a1a1a',
          overflow: 'hidden',
        }}
      />
      
      {/* Translated text with handwriting reveal */}
      {progress > 0.2 && (
        <div
          style={{
            position: 'absolute',
            left: x,
            top: y,
            fontFamily: "'Caveat', 'Patrick Hand', 'Kalam', Georgia, serif",
            fontSize: fontSize,
            color: 'white',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            width: w + 20,
          }}
        >
          {visibleText.split('').map((char, i) => (
            <span
              key={i}
              style={{
                display: 'inline-block',
                transform: `translateY(${Math.sin(i * 0.7) * 1.2}px)`,
                opacity: i === charsToShow - 1 ? 0.8 : 1,
              }}
            >
              {char}
            </span>
          ))}
          
          {/* Writing cursor */}
          {progress < 1 && (
            <span
              style={{
                display: 'inline-block',
                width: 2,
                height: fontSize * 0.7,
                backgroundColor: 'rgba(255,255,255,0.6)',
                marginLeft: 1,
                verticalAlign: 'middle',
              }}
            />
          )}
        </div>
      )}
    </>
  );
};

// =============================================================================
// Main composition
// =============================================================================

export const KhanLocalizedVideo: React.FC<KhanLocalizedVideoProps> = ({
  videoSrc,
  regionsData,
  videoWidth,
  videoHeight,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  
  const currentTime = frame / fps;
  
  // Scale factors if output resolution differs from source
  const scaleX = width / videoWidth;
  const scaleY = height / videoHeight;
  
  return (
    <AbsoluteFill>
      {/* Original Khan Academy video */}
      <Video src={videoSrc} />
      
      {/* Text overlays */}
      {regionsData.regions.map((region, index) => {
        // Is this region currently active?
        if (currentTime < region.startTime || currentTime > region.endTime) {
          return null;
        }
        
        // Calculate writing progress
        const writeDuration = region.stableTime - region.startTime;
        let progress: number;
        
        if (currentTime <= region.stableTime) {
          // Text is being "written" - use spring for natural feel
          const rawProgress = (currentTime - region.startTime) / writeDuration;
          progress = Math.min(rawProgress, 1);
        } else {
          progress = 1;
        }
        
        // Scale coordinates to output resolution
        const sx = region.x * scaleX;
        const sy = region.y * scaleY;
        const sw = region.w * scaleX;
        const sh = region.h * scaleY;
        const fontSize = (region.h - 4) * scaleY;
        
        return (
          <HandwritingText
            key={index}
            text={region.translatedText}
            x={sx}
            y={sy}
            w={sw}
            h={sh}
            progress={progress}
            fontSize={Math.max(fontSize, 16)}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// =============================================================================
// Example composition setup (for Root.tsx)
// =============================================================================

/*
// In your Root.tsx:

import { Composition } from 'remotion';
import { KhanLocalizedVideo } from './KhanLocalizedVideo';
import regionsData from './data/regions.json';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="KhanLocalized"
      component={KhanLocalizedVideo}
      durationInFrames={300}  // adjust to your video length * fps
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{
        videoSrc: '/khan_original.mp4',
        regionsData: regionsData,
        videoWidth: 1920,   // original video dimensions
        videoHeight: 1080,
      }}
    />
  );
};

// Render with: npx remotion render KhanLocalized output.mp4
*/
