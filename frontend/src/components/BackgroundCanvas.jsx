import { useCallback, useRef } from 'react';
import useDynamicShader from '../hooks/useDynamicShader';

export default function BackgroundCanvas({ onCoordsChange }) {
  const canvasContainerRef = useRef(null);
  const handleMouse = useCallback(
    (value) => {
      onCoordsChange(value);
    },
    [onCoordsChange]
  );

  useDynamicShader({
    containerRef: canvasContainerRef,
    onMouseTarget: handleMouse
  });

  return <div ref={canvasContainerRef} className="background-canvas" />;
}
