import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Cookie } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import {
  COOKIE_CONSENT_KEY,
  COOKIE_CONSENT_RESET_EVENT,
  COOKIE_CONSENT_VALUE,
  getCookie,
  setCookie,
} from '@/infrastructure/config/cookieStorage';

export function CookieConsentBanner() {
  const [visible, setVisible] = useState(
    () => getCookie(COOKIE_CONSENT_KEY) === null
  );

  useEffect(() => {
    const mostrar = () => setVisible(true);
    window.addEventListener(COOKIE_CONSENT_RESET_EVENT, mostrar);
    return () => window.removeEventListener(COOKIE_CONSENT_RESET_EVENT, mostrar);
  }, []);

  if (!visible) return null;

  const aceptar = () => {
    setCookie(COOKIE_CONSENT_KEY, COOKIE_CONSENT_VALUE);
    setVisible(false);
  };

  return (
    <section
      role="region"
      aria-label="Aviso de cookies"
      className="fixed inset-x-0 bottom-0 z-[60] border-t border-border-custom bg-surface px-4 py-4 shadow-[0_-4px_20px_rgba(0,0,0,0.12)] sm:px-6"
    >
      <div className="mx-auto flex max-w-[1200px] flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <Cookie
            className="mt-0.5 h-5 w-5 shrink-0 text-primary-orange"
            aria-hidden
          />
          <div>
            <h2 className="text-sm font-bold text-text-main">
              Aviso de cookies
            </h2>
            <p className="text-sm text-text-muted">
              Usamos una única cookie técnica para recordar que aceptaste este
              aviso. No hay cookies de seguimiento ni publicidad. Puedes ver el
              detalle en nuestra política de cookies.
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Link
            to="/cookies"
            className="text-sm font-bold text-primary-blue underline underline-offset-2"
          >
            Ver política
          </Link>
          <Button variant="primary" onClick={aceptar}>
            Aceptar
          </Button>
        </div>
      </div>
    </section>
  );
}
