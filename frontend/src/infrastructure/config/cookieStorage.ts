export const COOKIE_CONSENT_KEY = 'tallerconect_cookie_consent';
export const COOKIE_CONSENT_VALUE = 'aceptada';
export const COOKIE_CONSENT_RESET_EVENT = 'tallerconect:cookies-reset';

const COOKIE_MAX_AGE_SEGUNDOS = 60 * 60 * 24 * 365;

function leerCookies(): string {
  return typeof document === 'undefined' ? '' : document.cookie;
}

export function getCookie(nombre: string): string | null {
  const prefijo = `${encodeURIComponent(nombre)}=`;
  const entrada = leerCookies()
    .split(';')
    .map((parte) => parte.trim())
    .find((parte) => parte.startsWith(prefijo));

  return entrada ? decodeURIComponent(entrada.slice(prefijo.length)) : null;
}

export function setCookie(
  nombre: string,
  valor: string,
  maxAgeSegundos: number = COOKIE_MAX_AGE_SEGUNDOS
): void {
  if (typeof document === 'undefined') return;

  const seguro =
    typeof location !== 'undefined' && location.protocol === 'https:'
      ? '; Secure'
      : '';
  document.cookie = `${encodeURIComponent(nombre)}=${encodeURIComponent(
    valor
  )}; Path=/; Max-Age=${maxAgeSegundos}; SameSite=Lax${seguro}`;
}

export function removeCookie(nombre: string): void {
  if (typeof document === 'undefined') return;

  document.cookie = `${encodeURIComponent(
    nombre
  )}=; Path=/; Max-Age=0; SameSite=Lax`;
}
