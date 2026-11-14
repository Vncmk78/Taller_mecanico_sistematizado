import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { DEFAULT_DEBOUNCE_MS, useDebouncedValue } from './useDebouncedValue';

describe('useDebouncedValue', () => {
    afterEach(() => {
        vi.useRealTimers();
    });

    it('mantiene el valor anterior hasta que pasa el retardo', () => {
        vi.useFakeTimers();
        const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value), {
            initialProps: { value: 'a' },
        });

        rerender({ value: 'ab' });
        expect(result.current).toBe('a');

        act(() => {
            vi.advanceTimersByTime(DEFAULT_DEBOUNCE_MS - 1);
        });
        expect(result.current).toBe('a');

        act(() => {
            vi.advanceTimersByTime(1);
        });
        expect(result.current).toBe('ab');
    });

    it('reinicia el temporizador cuando el valor cambia antes de tiempo', () => {
        vi.useFakeTimers();
        const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value), {
            initialProps: { value: 'a' },
        });

        rerender({ value: 'ab' });
        act(() => {
            vi.advanceTimersByTime(200);
        });
        rerender({ value: 'abc' });
        act(() => {
            vi.advanceTimersByTime(200);
        });
        expect(result.current).toBe('a');

        act(() => {
            vi.advanceTimersByTime(100);
        });
        expect(result.current).toBe('abc');
    });

    it('devuelve el valor sin espera cuando el retardo es 0', () => {
        const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 0), {
            initialProps: { value: 'a' },
        });

        rerender({ value: 'ab' });
        expect(result.current).toBe('ab');
    });

    it('no actualiza el valor después de desmontar', () => {
        vi.useFakeTimers();
        const { rerender, unmount } = renderHook(({ value }) => useDebouncedValue(value), {
            initialProps: { value: 'a' },
        });

        rerender({ value: 'ab' });
        unmount();

        expect(() => {
            act(() => {
                vi.advanceTimersByTime(DEFAULT_DEBOUNCE_MS);
            });
        }).not.toThrow();
    });
});
