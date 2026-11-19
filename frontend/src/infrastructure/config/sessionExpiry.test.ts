import { describe, expect, it } from 'vitest';
import {
  decodeJwtPayload,
  getMinutosRestantes,
  getSessionExpiryMessage,
  getSessionExpiryStatus,
  getTokenExpiryMs,
  SESSION_WARNING_MS,
} from './sessionExpiry';
import { tokenConPayload, tokenConExpiracionEnSegundos } from '@/test/jwt';

const AHORA = 1_800_000_000_000; // ms epoch fijo para las comparaciones

describe('sessionExpiry: lectura del JWT', () => {
  it('decodifica el payload de un JWT con base64url', () => {
    const token = tokenConExpiracionEnSegundos(1_800_003_600);

    expect(decodeJwtPayload(token)).toMatchObject({
      sub: '1',
      roles: ['administrador'],
      exp: 1_800_003_600,
    });
  });

  it('devuelve null sin token o con una cantidad de partes distinta de tres', () => {
    expect(decodeJwtPayload(null)).toBeNull();
    expect(decodeJwtPayload('token-opaco')).toBeNull();
    expect(decodeJwtPayload('a.b')).toBeNull();
    expect(decodeJwtPayload('a.b.c.d')).toBeNull();
  });

  it('devuelve null si el payload no es base64/JSON válido', () => {
    expect(decodeJwtPayload('cabecera.no-es-base64!!.firma')).toBeNull();
    expect(decodeJwtPayload(`cabecera.${btoa('no-json')}.firma`)).toBeNull();
  });

  it('devuelve null si el JSON no es un objeto', () => {
    expect(decodeJwtPayload(`cabecera.${btoa('[1,2]')}.firma`)).toBeNull();
    expect(decodeJwtPayload(`cabecera.${btoa('null')}.firma`)).toBeNull();
    expect(decodeJwtPayload(`cabecera.${btoa('"texto"')}.firma`)).toBeNull();
  });

  it('extrae exp en milisegundos', () => {
    const token = tokenConExpiracionEnSegundos(1_800_003_600);
    expect(getTokenExpiryMs(token)).toBe(1_800_003_600_000);
  });

  it('no inventa exp cuando falta o no es un número positivo', () => {
    expect(getTokenExpiryMs(null)).toBeNull();
    expect(getTokenExpiryMs(tokenConPayload({ sub: '1' }))).toBeNull();
    expect(getTokenExpiryMs(tokenConPayload({ exp: '1800000000' }))).toBeNull();
    expect(getTokenExpiryMs(tokenConPayload({ exp: 0 }))).toBeNull();
    expect(getTokenExpiryMs(tokenConPayload({ exp: -5 }))).toBeNull();
    expect(getTokenExpiryMs(tokenConPayload({ exp: Number.POSITIVE_INFINITY }))).toBeNull();
  });
});

describe('sessionExpiry: estado de la sesión', () => {
  it('sin token no hay nada que anticipar', () => {
    expect(getSessionExpiryStatus(null, AHORA)).toBe('sin-token');
  });

  it('con más de la ventana de aviso sigue vigente', () => {
    expect(getSessionExpiryStatus(AHORA + SESSION_WARNING_MS + 1, AHORA)).toBe('vigente');
  });

  it('al entrar en la ventana de aviso queda por expirar', () => {
    expect(getSessionExpiryStatus(AHORA + SESSION_WARNING_MS, AHORA)).toBe('por-expirar');
    expect(getSessionExpiryStatus(AHORA + 1_000, AHORA)).toBe('por-expirar');
  });

  it('en el instante de expiración o después queda expirada', () => {
    expect(getSessionExpiryStatus(AHORA, AHORA)).toBe('expirada');
    expect(getSessionExpiryStatus(AHORA - 1, AHORA)).toBe('expirada');
  });

  it('acepta una ventana de aviso distinta', () => {
    expect(getSessionExpiryStatus(AHORA + 60_000, AHORA, 30_000)).toBe('vigente');
    expect(getSessionExpiryStatus(AHORA + 10_000, AHORA, 30_000)).toBe('por-expirar');
  });
});

describe('sessionExpiry: minutos y mensaje', () => {
  it('redondea los minutos hacia arriba y nunca baja de cero', () => {
    expect(getMinutosRestantes(AHORA + 1_000, AHORA)).toBe(1);
    expect(getMinutosRestantes(AHORA + 60_000, AHORA)).toBe(1);
    expect(getMinutosRestantes(AHORA + 60_001, AHORA)).toBe(2);
    expect(getMinutosRestantes(AHORA - 60_000, AHORA)).toBe(0);
  });

  it('con un minuto o menos avisa sin cifra', () => {
    expect(getSessionExpiryMessage(0)).toContain('está por expirar');
    expect(getSessionExpiryMessage(1)).toContain('está por expirar');
    expect(getSessionExpiryMessage(1)).not.toMatch(/\d/);
  });

  it('con más de un minuto muestra la cuenta', () => {
    expect(getSessionExpiryMessage(5)).toBe(
      'Tu sesión expirará en 5 minutos. Guarda tu trabajo e inicia sesión nuevamente.'
    );
  });
});
