import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SESSION_TICK_MS, SESSION_WARNING_MS } from '@/infrastructure/config/sessionExpiry';
import { tokenQueVenceEn, tokenVencido } from '@/test/jwt';
import { useSessionExpiry } from './useSessionExpiry';

const AHORA = 1_800_000_000_000;
const MINUTO = 60_000;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(AHORA));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('useSessionExpiry: cierre proactivo de la sesión', () => {
  it('sin token no programa nada ni avisa', () => {
    const onExpired = vi.fn();
    const { result } = renderHook(() => useSessionExpiry({ token: null, onExpired }));

    act(() => {
      vi.advanceTimersByTime(24 * 60 * MINUTO);
    });

    expect(result.current.minutosRestantes).toBeNull();
    expect(onExpired).not.toHaveBeenCalled();
  });

  it('con un token opaco no puede anticipar y deja actuar al 401', () => {
    const onExpired = vi.fn();
    const { result } = renderHook(() =>
      useSessionExpiry({ token: 'token-sin-formato-jwt', onExpired })
    );

    act(() => {
      vi.advanceTimersByTime(24 * 60 * MINUTO);
    });

    expect(result.current.minutosRestantes).toBeNull();
    expect(onExpired).not.toHaveBeenCalled();
  });

  it('avisa recién al entrar en la ventana de 5 minutos', () => {
    const onExpired = vi.fn();
    const token = tokenQueVenceEn(10 * MINUTO, AHORA);
    const { result } = renderHook(() => useSessionExpiry({ token, onExpired }));

    expect(result.current.minutosRestantes).toBeNull();

    act(() => {
      vi.advanceTimersByTime(10 * MINUTO - SESSION_WARNING_MS - 1_000);
    });
    expect(result.current.minutosRestantes).toBeNull();

    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    expect(result.current.minutosRestantes).toBe(5);
    expect(onExpired).not.toHaveBeenCalled();
  });

  it('actualiza la cuenta mientras se acerca la expiración', () => {
    const onExpired = vi.fn();
    const token = tokenQueVenceEn(10 * MINUTO, AHORA);
    const { result } = renderHook(() => useSessionExpiry({ token, onExpired }));

    act(() => {
      vi.advanceTimersByTime(5 * MINUTO);
    });
    expect(result.current.minutosRestantes).toBe(5);

    act(() => {
      vi.advanceTimersByTime(2 * MINUTO);
    });
    expect(result.current.minutosRestantes).toBe(3);
    expect(onExpired).not.toHaveBeenCalled();
  });

  it('cierra la sesión exactamente al vencer el token', () => {
    const onExpired = vi.fn();
    const token = tokenQueVenceEn(1_000, AHORA);
    const { result } = renderHook(() => useSessionExpiry({ token, onExpired }));

    expect(onExpired).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(3_000);
    });

    expect(result.current.minutosRestantes).toBeNull();
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(onExpired).toHaveBeenCalledWith(true);
  });

  it('un token ya vencido al montar se limpia sin anunciar expiración en uso', () => {
    const onExpired = vi.fn();
    renderHook(() => useSessionExpiry({ token: tokenVencido(AHORA), onExpired }));

    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(onExpired).toHaveBeenCalledWith(false);
  });

  it('no vuelve a avisar si el token cambia y el temporizador anterior se cancela', () => {
    const onExpired = vi.fn();
    const { rerender } = renderHook(
      ({ token }: { token: string }) => useSessionExpiry({ token, onExpired }),
      { initialProps: { token: tokenQueVenceEn(10 * MINUTO, AHORA) } }
    );

    rerender({ token: tokenQueVenceEn(1_000, AHORA) });

    act(() => {
      vi.advanceTimersByTime(3_000);
    });

    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(onExpired).toHaveBeenCalledWith(true);
  });

  it('al desmontar cancela los temporizadores y no cierra la sesión', () => {
    const onExpired = vi.fn();
    const { unmount } = renderHook(() =>
      useSessionExpiry({ token: tokenQueVenceEn(1_000, AHORA), onExpired })
    );

    unmount();

    act(() => {
      vi.advanceTimersByTime(3_000);
    });

    expect(onExpired).not.toHaveBeenCalled();
  });

  it('al volver a primer plano después del vencimiento cierra la sesión', () => {
    const onExpired = vi.fn();
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
    renderHook(() =>
      useSessionExpiry({ token: tokenQueVenceEn(10 * MINUTO, AHORA), onExpired })
    );

    // El temporizador no corre (pestaña dormida), pero el reloj sí avanzó.
    vi.setSystemTime(new Date(AHORA + 11 * MINUTO));
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(onExpired).toHaveBeenCalledWith(true);
  });

  it('el contador se actualiza con la cadencia configurada', () => {
    const token = tokenQueVenceEn(10 * MINUTO, AHORA);
    const { result } = renderHook(() => useSessionExpiry({ token, onExpired: vi.fn() }));

    act(() => {
      vi.advanceTimersByTime(5 * MINUTO + SESSION_TICK_MS);
    });

    expect(result.current.minutosRestantes).toBe(5);
  });
});
