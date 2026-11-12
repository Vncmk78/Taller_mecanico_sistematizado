/**
 * Ayudantes SOLO para tests: fabrican JWTs con la misma forma que emite MS1
 * (`sub`, `roles`, `exp`) sin firmarlos de verdad. La firma no se valida en el
 * cliente, así que basta con que el payload sea decodificable.
 */

function base64Url(valor: string): string {
  return btoa(valor).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function tokenConPayload(payload: Record<string, unknown>): string {
  const header = base64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const cuerpo = base64Url(JSON.stringify(payload));
  return `${header}.${cuerpo}.firma-falsa`;
}

/** Token que vence a `expiraEn` (segundos epoch). */
export function tokenConExpiracionEnSegundos(expiraEn: number): string {
  return tokenConPayload({ sub: '1', roles: ['administrador'], exp: expiraEn });
}

/** Token que vence dentro de `ms` milisegundos. */
export function tokenQueVenceEn(ms: number, ahora: number = Date.now()): string {
  return tokenConExpiracionEnSegundos(Math.ceil((ahora + ms) / 1000));
}

/** Token cuyo `exp` ya pasó. */
export function tokenVencido(ahora: number = Date.now()): string {
  return tokenConExpiracionEnSegundos(Math.floor(ahora / 1000) - 60);
}
