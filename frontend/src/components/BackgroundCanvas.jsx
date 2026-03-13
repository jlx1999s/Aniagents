import { useCallback, useRef } from 'react';
import useDynamicShader from '../hooks/useDynamicShader';

export default function BackgroundCanvas({ onCoordsChange, isAnimated }) {
  const canvasContainerRef = useRef(null);
  const handleMouse = useCallback(
    (value) => {
      onCoordsChange(value);
    },
    [onCoordsChange]
  );

  useDynamicShader({
    containerRef: canvasContainerRef,
    onMouseTarget: handleMouse,
    isAnimated
  });

  return <div ref={canvasContainerRef} className={`background-canvas ${isAnimated ? '' : 'background-canvas-static'}`} />;
}
