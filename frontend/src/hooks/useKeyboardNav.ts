import { useEffect, useCallback } from 'react';

export interface UseKeyboardNavOptions {
  itemCount: number;
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
  onPeek?: (index: number) => void;
  onDismiss?: () => void;
  onTogglePause?: () => void;
  searchInputRef?: React.RefObject<HTMLInputElement | null>;
  enabled?: boolean;
}

/**
 * Enterprise Keyboard Navigation Hook
 * Implements Linear-style keyboard navigation (j/k, Space, Esc, /, p).
 * Automatically suppresses shortcuts when input/textarea/select fields are focused.
 */
export function useKeyboardNav({
  itemCount,
  selectedIndex,
  onSelectIndex,
  onPeek,
  onDismiss,
  onTogglePause,
  searchInputRef,
  enabled = true,
}: UseKeyboardNavOptions) {
  const isInputFocused = useCallback(() => {
    const active = document.activeElement;
    if (!active) return false;
    const tagName = active.tagName.toUpperCase();
    return (
      tagName === 'INPUT' ||
      tagName === 'TEXTAREA' ||
      tagName === 'SELECT' ||
      (active as HTMLElement).isContentEditable
    );
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Allow escape to dismiss even if an input is focused (e.g. blur search on Esc)
      if (e.key === 'Escape') {
        if (isInputFocused()) {
          (document.activeElement as HTMLElement)?.blur();
          return;
        }
        if (onDismiss) {
          e.preventDefault();
          onDismiss();
        }
        return;
      }

      // If an input is focused, don't hijack typing keys
      if (isInputFocused()) {
        return;
      }

      // Search focus shortcut: '/'
      if (e.key === '/' && searchInputRef?.current) {
        e.preventDefault();
        searchInputRef.current.focus();
        return;
      }

      // Stream pause shortcut: 'p' or 'P'
      if ((e.key === 'p' || e.key === 'P') && onTogglePause) {
        e.preventDefault();
        onTogglePause();
        return;
      }

      // Navigate down: 'j' or 'ArrowDown'
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (itemCount === 0) return;
        const nextIndex = selectedIndex < itemCount - 1 ? selectedIndex + 1 : 0;
        onSelectIndex(nextIndex);
        return;
      }

      // Navigate up: 'k' or 'ArrowUp'
      if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (itemCount === 0) return;
        const prevIndex = selectedIndex > 0 ? selectedIndex - 1 : itemCount - 1;
        onSelectIndex(prevIndex);
        return;
      }

      // Peek / inspect toggle: ' ' (Space) or 'Enter'
      if ((e.key === ' ' || e.key === 'Enter') && onPeek) {
        if (selectedIndex >= 0 && selectedIndex < itemCount) {
          e.preventDefault();
          onPeek(selectedIndex);
        }
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    enabled,
    itemCount,
    selectedIndex,
    onSelectIndex,
    onPeek,
    onDismiss,
    onTogglePause,
    searchInputRef,
    isInputFocused,
  ]);
}
