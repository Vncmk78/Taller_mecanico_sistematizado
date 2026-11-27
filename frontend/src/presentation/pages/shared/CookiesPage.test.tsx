import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { CookiesPage } from '@/presentation/pages/shared/CookiesPage';
import {
  COOKIE_CONSENT_KEY,
  COOKIE_CONSENT_RESET_EVENT,
  COOKIE_CONSENT_VALUE,
  getCookie,
  setCookie,
} from '@/infrastructure/config/cookieStorage';

function renderPage() {
  return render(
    <MemoryRouter>
      <CookiesPage />
    </MemoryRouter>
  );
}

describe('CookiesPage', () => {
  it('explica la cookie técnica y que no hay cookies de seguimiento', () => {
    renderPage();

    expect(
      screen.getByRole('heading', {
        name: 'Cookies y almacenamiento local',
        level: 1,
      })
    ).toBeInTheDocument();
    expect(screen.getByText(COOKIE_CONSENT_KEY)).toBeInTheDocument();
    expect(
      screen.getByText(/No utilizamos cookies de análisis, publicidad ni seguimiento/)
    ).toBeInTheDocument();
  });

  it('documenta las claves de almacenamiento local', () => {
    renderPage();

    expect(screen.getByText('token')).toBeInTheDocument();
    expect(
      screen.getByText('tallerconect:orders-filters:pageSize')
    ).toBeInTheDocument();
  });

  it('muestra el estado actual de la cookie', () => {
    setCookie(COOKIE_CONSENT_KEY, COOKIE_CONSENT_VALUE);
    renderPage();

    expect(screen.getByText(/Estado actual:/)).toHaveTextContent('aceptada');
  });

  it('restablece la cookie y avisa al banner para que vuelva a aparecer', () => {
    setCookie(COOKIE_CONSENT_KEY, COOKIE_CONSENT_VALUE);
    const alRestablecer = vi.fn();
    window.addEventListener(COOKIE_CONSENT_RESET_EVENT, alRestablecer);
    renderPage();

    fireEvent.click(
      screen.getByRole('button', { name: 'Restablecer aviso de cookies' })
    );

    expect(getCookie(COOKIE_CONSENT_KEY)).toBeNull();
    expect(alRestablecer).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Estado actual:/)).toHaveTextContent('sin registrar');
    window.removeEventListener(COOKIE_CONSENT_RESET_EVENT, alRestablecer);
  });
});
