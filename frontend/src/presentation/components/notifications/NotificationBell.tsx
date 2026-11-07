import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Bell, CheckCheck, ExternalLink, X } from 'lucide-react';
import type { Notification } from '@/domain/entities/Notification';
import { notificationService } from '@/infrastructure/api/NotificationService';

function formatFecha(fechaIso: string): string {
  const fecha = new Date(fechaIso);
  if (Number.isNaN(fecha.getTime())) return '';
  return fecha.toLocaleString('es-CL', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface NotificationBellProps {
  className?: string;
  tone?: 'light' | 'dark';
}

function getCenterPath(pathname: string): string | null {
  if (pathname.startsWith('/admin')) return '/admin/notificaciones';
  if (pathname.startsWith('/client')) return '/client/notificaciones';
  if (pathname.startsWith('/mechanic')) return '/mechanic/notificaciones';
  return null;
}

export function NotificationBell({ className = '', tone = 'light' }: NotificationBellProps) {
  const { pathname } = useLocation();
  const centerPath = getCenterPath(pathname);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [noLeidas, setNoLeidas] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inflightRef = useRef(false);
  const lastFetchAtRef = useRef(0);

  const cargar = useCallback(async (silencioso = false) => {
    if (inflightRef.current) return;
    inflightRef.current = true;
    if (!silencioso) setLoading(true);
    setError(null);
    try {
      const res = await notificationService.getMyNotifications({ limit: 15 });
      setItems(res.items);
      setNoLeidas(res.noLeidas);
      lastFetchAtRef.current = Date.now();
    } catch {
      setError('No se pudieron cargar los avisos.');
    } finally {
      inflightRef.current = false;
      if (!silencioso) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void cargar(true);
    const id = window.setInterval(() => void cargar(true), 60000);
    return () => window.clearInterval(id);
  }, [cargar]);

  useEffect(() => {
    if (!open) return;
    // Evita solicitud redundante si la data se cargó recientemente (intervalo/mount).
    if (Date.now() - lastFetchAtRef.current < 15000) return;
    void cargar();
  }, [open, cargar]);

  useEffect(() => {
    if (!open) return;
    const closeButton = dialogRef.current?.querySelector<HTMLElement>('button[aria-label="Cerrar avisos"]');
    closeButton?.focus();
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const marcarLeida = async (id: string) => {
    try {
      await notificationService.markAsRead(id);
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, leida: true } : n)));
      setNoLeidas((prev) => Math.max(0, prev - 1));
    } catch {
      // Ignorar; el usuario puede reintentar
    }
  };

  const marcarTodas = async () => {
    try {
      await notificationService.markAllAsRead();
      setItems((prev) => prev.map((n) => ({ ...n, leida: true })));
      setNoLeidas(0);
    } catch {
      // Ignorar
    }
  };

  const badgeText = noLeidas > 99 ? '99+' : String(noLeidas);
  const triggerClass =
    tone === 'dark'
      ? 'text-white/90 hover:text-white hover:bg-white/10'
      : 'text-text-muted hover:text-text-main hover:bg-bg-secondary';

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        aria-label={noLeidas > 0 ? `Notificaciones, ${noLeidas} sin leer` : 'Notificaciones'}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        className={`relative inline-flex items-center justify-center w-10 h-10 rounded-lg transition-colors ${triggerClass}`}
      >
        <Bell className="w-5 h-5" aria-hidden />
        {noLeidas > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-primary-orange text-white text-[10px] font-bold leading-[18px] text-center">
            {badgeText}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="false"
          aria-label="Avisos y notificaciones"
          className="absolute right-0 mt-2 w-[min(92vw,360px)] max-h-[70vh] overflow-hidden rounded-xl border border-border-custom bg-surface text-text-main shadow-xl z-[70] flex flex-col"
        >
          <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-border-custom bg-surface-elevated">
            <div>
              <h3 className="text-sm font-bold">Avisos</h3>
              <p className="text-xs text-text-muted">
                {noLeidas > 0 ? `${noLeidas} sin leer` : 'Sin avisos pendientes'}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {noLeidas > 0 && (
                <button
                  type="button"
                  onClick={() => void marcarTodas()}
                  className="inline-flex items-center gap-1 px-2 py-1.5 rounded-md text-xs font-medium text-primary-blue hover:bg-primary-blue/10"
                  title="Marcar todas como leídas"
                >
                  <CheckCheck className="w-4 h-4" aria-hidden />
                  <span className="hidden sm:inline">Leer todas</span>
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Cerrar avisos"
                className="p-1.5 rounded-md text-text-muted hover:text-text-main hover:bg-bg-secondary"
              >
                <X className="w-4 h-4" aria-hidden />
              </button>
            </div>
          </div>

          <div className="overflow-y-auto">
            {loading && (
              <p className="px-4 py-6 text-sm text-text-muted text-center">Cargando avisos...</p>
            )}
            {!loading && error && (
              <p className="px-4 py-6 text-sm text-status-red text-center">{error}</p>
            )}
            {!loading && !error && items.length === 0 && (
              <p className="px-4 py-6 text-sm text-text-muted text-center">
                No hay notificaciones disponibles.
              </p>
            )}
            {!loading && !error && items.length > 0 && (
              <ul className="divide-y divide-border-custom">
                {items.map((n) => (
                  <li key={n.id} className={n.leida ? 'bg-surface' : 'bg-primary-blue/5'}>
                    <button
                      type="button"
                      onClick={() => {
                        if (!n.leida) void marcarLeida(n.id);
                      }}
                      className="w-full text-left px-4 py-3 hover:bg-bg-secondary/60 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className={`text-sm ${n.leida ? 'font-medium text-text-main' : 'font-semibold text-text-main'}`}>
                          {n.titulo}
                        </p>
                        {!n.leida && (
                          <span className="mt-1 w-2 h-2 rounded-full bg-primary-orange shrink-0" aria-label="No leída" />
                        )}
                      </div>
                      <p className="text-xs text-text-muted mt-1 line-clamp-2">{n.mensaje}</p>
                      <p className="text-[11px] text-text-muted mt-1.5">{formatFecha(n.creadaEn)}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {centerPath && (
            <div className="border-t border-border-custom bg-surface-elevated px-3 py-2">
              <Link
                to={centerPath}
                onClick={() => setOpen(false)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-primary-blue hover:bg-primary-blue/10">
                <ExternalLink className="w-4 h-4" aria-hidden />
                Ver centro de avisos
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
