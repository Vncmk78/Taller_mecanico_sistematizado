import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { CookieConsentBanner } from '@/presentation/components/cookies/CookieConsentBanner';
import {
  COOKIE_CONSENT_KEY,
  COOKIE_CONSENT_RESET_EVENT,
  COOKIE_CONSENT_VALUE,
  getCookie,
  setCookie,
} from '@/infrastructure/config/cookieStorage';

function renderBanner() {
  return render(
    <MemoryRouter>
      <CookieConsentBanner />
    </MemoryRouter>
  );
}

describe('CookieConsentBanner', () => {
  it('muestra el aviso y enlaza a la política cuando no hay cookie', () => {
    renderBanner();

    expect(
      screen.getByRole('region', { name: 'Aviso de cookies' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aceptar' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver política' })).toHaveAttribute(
      'href',
      '/cookies'
    );
  });

  it('guarda la cookie y oculta el aviso al aceptar', () => {
    renderBanner();

    fireEvent.click(screen.getByRole('button', { name: 'Aceptar' }));

    expect(getCookie(COOKIE_CONSENT_KEY)).toBe(COOKIE_CONSENT_VALUE);
    expect(
      screen.queryByRole('region', { name: 'Aviso de cookies' })
    ).not.toBeInTheDocument();
  });

  it('no muestra el aviso si la cookie ya fue aceptada', () => {
    setCookie(COOKIE_CONSENT_KEY, COOKIE_CONSENT_VALUE);
    renderBanner();

    expect(
      screen.queryByRole('region', { name: 'Aviso de cookies' })
    ).not.toBeInTheDocument();
  });

  it('vuelve a mostrar el aviso cuando se restablece la decisión', () => {
    setCookie(COOKIE_CONSENT_KEY, COOKIE_CONSENT_VALUE);
    renderBanner();

    expect(
      screen.queryByRole('region', { name: 'Aviso de cookies' })
    ).not.toBeInTheDocument();

    fireEvent(window, new Event(COOKIE_CONSENT_RESET_EVENT));

    expect(
      screen.getByRole('region', { name: 'Aviso de cookies' })
    ).toBeInTheDocument();
  });
});
