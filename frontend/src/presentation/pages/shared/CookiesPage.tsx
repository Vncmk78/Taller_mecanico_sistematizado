import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Cookie, Mail, Phone, Settings, Wrench } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import {
  COOKIE_CONSENT_KEY,
  COOKIE_CONSENT_RESET_EVENT,
  getCookie,
  removeCookie,
} from '@/infrastructure/config/cookieStorage';

const clavesAlmacenamientoLocal = [
  {
    clave: 'token',
    uso: 'Guarda el JWT de la sesión iniciada. Se elimina al cerrar sesión.',
  },
  {
    clave: 'tallerconect:orders-filters:search',
    uso: 'Conserva el texto de búsqueda de los listados de órdenes.',
  },
  {
    clave: 'tallerconect:orders-filters:estado',
    uso: 'Conserva el filtro de estado de los listados de órdenes.',
  },
  {
    clave: 'tallerconect:orders-filters:page',
    uso: 'Conserva la página visitada en los listados de órdenes.',
  },
  {
    clave: 'tallerconect:orders-filters:pageSize',
    uso: 'Conserva el tamaño de página elegido en los listados de órdenes.',
  },
];

export function CookiesPage() {
  const [estadoConsentimiento, setEstadoConsentimiento] = useState(
    () => getCookie(COOKIE_CONSENT_KEY) ?? 'sin registrar'
  );

  const restablecer = () => {
    removeCookie(COOKIE_CONSENT_KEY);
    setEstadoConsentimiento('sin registrar');
    window.dispatchEvent(new CustomEvent(COOKIE_CONSENT_RESET_EVENT));
  };

  return (
    <div className="min-h-[var(--viewport-height)] flex flex-col animate-fade-in">
      <nav className="flex flex-wrap justify-between items-center gap-3 px-4 sm:px-6 lg:px-12 py-4 lg:py-5 border-b border-border-custom bg-surface sticky top-0 z-50">
        <Link
          to="/"
          className="flex items-center gap-2.5 text-xl sm:text-2xl font-bold text-text-main no-underline"
        >
          <span className="relative inline-block w-[35px] h-[35px] text-text-muted">
            <Settings className="absolute left-0 top-0 w-6 h-6" />
            <Wrench
              className="absolute left-3 top-3 w-4 h-4 text-primary-orange -rotate-15"
              aria-hidden
            />
          </span>
          TallerConect
        </Link>
        <Link
          to="/"
          className="bg-primary-blue text-white px-4 sm:px-6 py-2.5 sm:py-3 rounded-lg font-bold text-sm sm:text-base transition-all duration-300 shadow-[0_4px_15px_rgba(21,40,63,0.25)] hover:bg-primary-blue-hover hover:-translate-y-0.5 no-underline whitespace-nowrap"
        >
          Volver al Inicio
        </Link>
      </nav>

      <main
        id="contenido-principal"
        tabIndex={-1}
        className="flex-grow focus:outline-none px-4 sm:px-6 lg:px-12 py-10 sm:py-14"
      >
        <GlassCard className="mx-auto w-full max-w-[900px] p-6 sm:p-10">
          <div className="flex items-center gap-3">
            <Cookie className="h-9 w-9 text-primary-orange" aria-hidden />
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-text-main">
                Cookies y almacenamiento local
              </h1>
              <p className="text-sm text-text-muted">Actualizado el 27-11-2026</p>
            </div>
          </div>

          <section aria-labelledby="resumen-cookies" className="mt-8">
            <h2
              id="resumen-cookies"
              className="text-xl font-bold text-text-main"
            >
              Resumen
            </h2>
            <p className="mt-2 text-text-muted">
              TallerConect usa <strong>una sola cookie técnica</strong> para
              recordar que viste y aceptaste el aviso de cookies. No utilizamos
              cookies de análisis, publicidad ni seguimiento de terceros. El
              resto de la información se guarda en el almacenamiento local de tu
              navegador, que no es una cookie.
            </p>
          </section>

          <section aria-labelledby="tabla-cookies" className="mt-8">
            <h2
              id="tabla-cookies"
              className="text-xl font-bold text-text-main"
            >
              Cookie utilizada
            </h2>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-left text-sm">
                <caption className="sr-only">
                  Detalle de la cookie utilizada por TallerConect
                </caption>
                <thead>
                  <tr className="border-b border-border-custom">
                    <th scope="col" className="py-2 pr-4 font-bold text-text-main">
                      Nombre
                    </th>
                    <th scope="col" className="py-2 pr-4 font-bold text-text-main">
                      Finalidad
                    </th>
                    <th scope="col" className="py-2 pr-4 font-bold text-text-main">
                      Tipo
                    </th>
                    <th scope="col" className="py-2 pr-4 font-bold text-text-main">
                      Duración
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-border-custom align-top">
                    <th scope="row" className="py-3 pr-4 text-text-main">
                      <code className="rounded bg-bg-secondary px-2 py-1 text-xs">
                        {COOKIE_CONSENT_KEY}
                      </code>
                    </th>
                    <td className="py-3 pr-4 text-text-muted">
                      Recordar tu aceptación del aviso para no volver a
                      mostrarlo.
                    </td>
                    <td className="py-3 pr-4 text-text-muted">
                      Propia, técnica y necesaria.
                    </td>
                    <td className="py-3 pr-4 text-text-muted">1 año.</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Estado actual: <strong>{estadoConsentimiento}</strong>.
            </p>
          </section>

          <section aria-labelledby="almacenamiento-local" className="mt-8">
            <h2
              id="almacenamiento-local"
              className="text-xl font-bold text-text-main"
            >
              Almacenamiento local (no son cookies)
            </h2>
            <p className="mt-2 text-text-muted">
              Estas claves viven en tu navegador y no se envían como cookies:
            </p>
            <ul className="mt-3 list-disc space-y-2 pl-6 text-sm text-text-muted">
              {clavesAlmacenamientoLocal.map(({ clave, uso }) => (
                <li key={clave}>
                  <code className="rounded bg-bg-secondary px-2 py-1 text-xs text-text-main">
                    {clave}
                  </code>{' '}
                  — {uso}
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="cambiar-decision" className="mt-8">
            <h2
              id="cambiar-decision"
              className="text-xl font-bold text-text-main"
            >
              Cambiar tu decisión
            </h2>
            <p className="mt-2 text-text-muted">
              Puedes borrar la cookie desde la configuración de tu navegador o
              usar el siguiente botón. El aviso volverá a aparecer.
            </p>
            <Button variant="secondary" onClick={restablecer} className="mt-4">
              Restablecer aviso de cookies
            </Button>
          </section>
        </GlassCard>
      </main>

      <footer className="flex flex-col sm:flex-row gap-2 sm:justify-between sm:items-center px-4 sm:px-6 lg:px-12 py-8 bg-primary-blue text-white text-sm text-center sm:text-left">
        <span>TallerConect</span>
        <div className="leading-relaxed text-white/80">
          <Phone className="w-4 inline text-white/60 mr-1" aria-hidden /> +443 379
          771
          <br />
          <Mail className="w-4 inline text-white/60 mr-1" aria-hidden />{' '}
          mecanica@sistema.cl
        </div>
      </footer>
    </div>
  );
}
