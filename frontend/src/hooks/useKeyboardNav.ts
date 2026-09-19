import { useEffect, useCallback } from 'react';

export interface UseKeyboardNavOptions {
  itemCount: number;
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
  onPeek?: (index: number) => void;
  onDismiss?: () => void;
  onTogglePause?: () => void;
  searchInputRef?: React.RefObject<HTMLInputElement | null>;
  containerRef?: React.RefObject<HTMLElement | null>;
  enabled?: boolean;
}

/**
 * Enterprise Keyboard Navigation Hook
 * Implements Linear-style keyboard navigation (j/k, Space, Esc, /, p).
 * Automatically suppresses shortcuts when input/textarea/select fields are focused.
 * Scopes arrow keys and Space to active table/grid focus to preserve native browser scrolling.
 */
export function useKeyboardNav({
  itemCount,
  selectedIndex,
  onSelectIndex,
  onPeek,
  onDismiss,
  onTogglePause,
  searchInputRef,
  containerRef,
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

  const isTableOrContainerFocused = useCallback(() => {
    const active = document.activeElement;
    if (!active) return false;
    if (containerRef?.current && (containerRef.current.contains(active) || containerRef.current === active)) {
      return true;
    }
    return Boolean(active.closest('table, [role="table"], [role="grid"], [role="listbox"], [data-keyboard-nav-container]'));
  }, [containerRef]);

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

      // Do not hijack browser shortcuts or hotkeys with modifiers
      if (e.ctrlKey || e.metaKey || e.altKey) {
        return;
      }

      // Search focus shortcut: '/'
      if (e.key === '/' && searchInputRef?.current) {
        e.preventDefault();
        searchInputRef.current.focus();
        return;
      }

      // Stream pause shortcut: 'p' or 'P'
      if (e.key.toLowerCase() === 'p' && onTogglePause) {
        e.preventDefault();
        onTogglePause();
        return;
      }

      // Navigate down: 'j' / 'J' (global) or 'ArrowDown' (scoped to table/container focus)
      if (e.key.toLowerCase() === 'j' || e.code === 'KeyJ' || e.key === 'ArrowDown') {
        if (e.key === 'ArrowDown' && !isTableOrContainerFocused()) {
          return; // Allow native page scroll
        }
        e.preventDefault();
        if (itemCount === 0) return;
        const nextIndex = selectedIndex < itemCount - 1 ? selectedIndex + 1 : 0;
        onSelectIndex(nextIndex);
        return;
      }

      // Navigate up: 'k' / 'K' (global) or 'ArrowUp' (scoped to table/container focus)
      if (e.key.toLowerCase() === 'k' || e.code === 'KeyK' || e.key === 'ArrowUp') {
        if (e.key === 'ArrowUp' && !isTableOrContainerFocused()) {
          return; // Allow native page scroll
        }
        e.preventDefault();
        if (itemCount === 0) return;
        const prevIndex = selectedIndex > 0 ? selectedIndex - 1 : itemCount - 1;
        onSelectIndex(prevIndex);
        return;
      }

      // Peek / inspect toggle: ' ' (Space) or 'Enter'
      if (e.key === ' ' || e.key === 'Spacebar' || e.code === 'Space' || e.key === 'Enter') {
        if (onPeek && selectedIndex >= 0 && selectedIndex < itemCount) {
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
    isTableOrContainerFocused,
  ]);
}
