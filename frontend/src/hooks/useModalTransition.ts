import { useState, useEffect } from 'react';

/**
 * Hook to coordinate two-way smooth entry (pop up) and exit (going back)
 * animations for modal dialogs and overlay sheets.
 */
export function useModalTransition(isOpen: boolean, durationMs: number = 220) {
  const [isRendered, setIsRendered] = useState(isOpen);
  const [isVisible, setIsVisible] = useState(isOpen);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let raf1: number | undefined;
    let raf2: number | undefined;

    if (isOpen) {
      setIsRendered(true);
      // Double rAF ensures browser paints initial state before transition begins
      raf1 = requestAnimationFrame(() => {
        raf2 = requestAnimationFrame(() => {
          setIsVisible(true);
        });
      });
    } else {
      setIsVisible(false);
      timer = setTimeout(() => {
        setIsRendered(false);
      }, durationMs + 20);
    }

    return () => {
      if (timer) clearTimeout(timer);
      if (raf1) cancelAnimationFrame(raf1);
      if (raf2) cancelAnimationFrame(raf2);
    };
  }, [isOpen, durationMs]);

  return { isRendered, isVisible };
}
