import { useState, useEffect } from 'react';

/**
 * Manages two-way smooth transition states for accordion expand (going down)
 * and collapse (going up).
 *
 * Guarantees:
 * 1. Mounts DOM element, then applies expanded class on next paint for a smooth downward slide.
 * 2. Removes expanded class immediately on close for a smooth upward slide, then unmounts DOM element after the transition duration.
 * 3. Honors initial state without running unnecessary animations on initial page load.
 */
export function useAccordionTransition(isOpen: boolean, durationMs: number = 280) {
  const [isRendered, setIsRendered] = useState(isOpen);
  const [isExpanded, setIsExpanded] = useState(isOpen);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let rafId1: number | undefined;
    let rafId2: number | undefined;

    if (isOpen) {
      setIsRendered(true);
      // Double requestAnimationFrame ensures browser commits the 0fr layout before transitioning to 1fr
      rafId1 = requestAnimationFrame(() => {
        rafId2 = requestAnimationFrame(() => {
          setIsExpanded(true);
        });
      });
    } else {
      setIsExpanded(false);
      timer = setTimeout(() => {
        setIsRendered(false);
      }, durationMs + 20);
    }

    return () => {
      if (timer) clearTimeout(timer);
      if (rafId1) cancelAnimationFrame(rafId1);
      if (rafId2) cancelAnimationFrame(rafId2);
    };
  }, [isOpen, durationMs]);

  return { isRendered, isExpanded };
}
