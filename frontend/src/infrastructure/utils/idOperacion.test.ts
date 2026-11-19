import { afterEach, describe, expect, it, vi } from 'vitest';
import { generarIdOperacion } from '@/infrastructure/utils/idOperacion';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('generarIdOperacion: compatibilidad de la clave de idempotencia', () => {
  it('usa crypto.randomUUID cuando está disponible', () => {
    const randomUUID = vi.fn(() => 'uuid-del-navegador');
    vi.stubGlobal('crypto', { randomUUID });

    expect(generarIdOperacion()).toBe('uuid-del-navegador');
    expect(randomUUID).toHaveBeenCalledTimes(1);
  });

  it('genera un UUID v4 con getRandomValues si randomUUID no existe', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (destino: Uint8Array) => {
        destino.fill(0xab);
        return destino;
      },
    });

    expect(generarIdOperacion()).toMatch(UUID_V4);
  });

  it('no lanza si crypto no existe', () => {
    vi.stubGlobal('crypto', undefined);

    expect(generarIdOperacion()).toMatch(UUID_V4);
  });

  it('genera claves distintas en llamadas sucesivas', () => {
    const ids = new Set(Array.from({ length: 50 }, () => generarIdOperacion()));

    expect(ids.size).toBe(50);
  });
});
