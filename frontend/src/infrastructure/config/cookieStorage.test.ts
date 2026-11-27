import { describe, expect, it } from 'vitest';
import {
  COOKIE_CONSENT_KEY,
  COOKIE_CONSENT_VALUE,
  getCookie,
  removeCookie,
  setCookie,
} from '@/infrastructure/config/cookieStorage';

describe('cookieStorage', () => {
  it('devuelve null si la cookie no existe', () => {
    expect(getCookie(COOKIE_CONSENT_KEY)).toBeNull();
  });

  it('guarda y lee la cookie de consentimiento', () => {
    setCookie(COOKIE_CONSENT_KEY, COOKIE_CONSENT_VALUE);

    expect(getCookie(COOKIE_CONSENT_KEY)).toBe(COOKIE_CONSENT_VALUE);
    expect(document.cookie).toContain(
      `${COOKIE_CONSENT_KEY}=${COOKIE_CONSENT_VALUE}`
    );
  });

  it('elimina la cookie de consentimiento', () => {
    setCookie(COOKIE_CONSENT_KEY, COOKIE_CONSENT_VALUE);
    removeCookie(COOKIE_CONSENT_KEY);

    expect(getCookie(COOKIE_CONSENT_KEY)).toBeNull();
  });
});
