/**
 * Utilidades para saber cuándo vence el JWT de la sesión sin consultar al
 * servidor. El token de MS1 incluye `exp` (segundos epoch); decodificarlo en el
 * cliente sirve solo para la experiencia de uso: la autorización real la sigue
 * validando cada microservicio.
 *
 * No se valida la firma: el navegador no tiene la clave y no debe tenerla. Un
 * token manipulado con un `exp` futuro no otorga permisos, solo retrasa el
 * cierre local hasta que la API responda 401 (que se maneja igual).
 */

/** Tiempo antes de la expiración en que se avisa al usuario. */
export const SESSION_WARNING_MS = 5 * 60 * 1000;

/** Cadencia del contador mientras la sesión está por expirar. */
export const SESSION_TICK_MS = 30 * 1000;

export type SessionExpiryStatus = 'sin-token' | 'vigente' | 'por-expirar' | 'expirada';

/** Decodifica el payload de un JWT (segunda parte) sin verificar la firma. */
export function decodeJwtPayload(token: string | null): Record<string, unknown> | null {
  if (!token) return null;
  const partes = token.split('.');
  if (partes.length !== 3) return null;

  try {
    const base64 = partes[1].replace(/-/g, '+').replace(/_/g, '/');
    const relleno = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=');
    const json = atob(relleno);
    const payload: unknown = JSON.parse(json);
    if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) return null;
    return payload as Record<string, unknown>;
  } catch {
    // Token opaco, base64 inválido o JSON malformado: no hay exp que leer.
    return null;
  }
}

/** Expiración del token en milisegundos epoch, o null si no se puede leer. */
export function getTokenExpiryMs(token: string | null): number | null {
  const exp = decodeJwtPayload(token)?.exp;
  if (typeof exp !== 'number' || !Number.isFinite(exp) || exp <= 0) return null;
  return exp * 1000;
}

export function getSessionExpiryStatus(
  expiraEnMs: number | null,
  ahoraMs: number = Date.now(),
  avisoMs: number = SESSION_WARNING_MS
): SessionExpiryStatus {
  if (expiraEnMs === null) return 'sin-token';
  const restante = expiraEnMs - ahoraMs;
  if (restante <= 0) return 'expirada';
  if (restante <= avisoMs) return 'por-expirar';
  return 'vigente';
}

/** Minutos completos que faltan, redondeando hacia arriba (nunca negativo). */
export function getMinutosRestantes(expiraEnMs: number, ahoraMs: number = Date.now()): number {
  return Math.max(0, Math.ceil((expiraEnMs - ahoraMs) / 60_000));
}

export function getSessionExpiryMessage(minutosRestantes: number): string {
  if (minutosRestantes <= 1) {
    return 'Tu sesión está por expirar. Guarda tu trabajo e inicia sesión nuevamente.';
  }
  return `Tu sesión expirará en ${minutosRestantes} minutos. Guarda tu trabajo e inicia sesión nuevamente.`;
}
