import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { NotificationDeliveryPanel } from '@/presentation/components/notifications/NotificationDeliveryPanel';
import { Bell, CheckCheck, RefreshCw } from 'lucide-react';
import type { Notification } from '@/domain/entities/Notification';
import { notificationService } from '@/infrastructure/api/NotificationService';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';

type FiltroLectura = 'todas' | 'no-leidas';

function formatFecha(fechaIso: string): string {
  const fecha = new Date(fechaIso);
  if (Number.isNaN(fecha.getTime())) return '';
  return fecha.toLocaleString('es-CL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function tipoLabel(tipo: string): string {
  const limpio = tipo?.trim();
  if (!limpio) return 'Aviso';
  return limpio.replace(/[_-]+/g, ' ');
}

export function NotificationsPage() {
  const [filtro, setFiltro] = useState<FiltroLectura>('todas');
  const [items, setItems] = useState<Notification[]>([]);
  const [total, setTotal] = useState(0);
  const [noLeidas, setNoLeidas] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const requestSeqRef = useRef(0);

  const cargar = useCallback(async (modo: 'initial' | 'refresh' = 'initial') => {
    const seq = ++requestSeqRef.current;
    if (modo === 'initial') setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const res = await notificationService.getMyNotifications({
        soloNoLeidas: filtro === 'no-leidas',
        limit: 100,
      });
      if (seq !== requestSeqRef.current) return; // respuesta obsoleta (cambio de filtro/refresco)
      setItems(res.items);
      setTotal(res.total);
      setNoLeidas(res.noLeidas);
    } catch {
      if (seq !== requestSeqRef.current) return;
      setError('No se pudieron cargar las notificaciones.');
    } finally {
      if (seq === requestSeqRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [filtro]);

  useEffect(() => {
    void cargar('initial');
  }, [cargar]);

  const marcarLeida = async (id: string) => {
    try {
      await notificationService.markAsRead(id);
      setItems((prev) =>
        filtro === 'no-leidas'
          ? prev.filter((n) => n.id !== id)
          : prev.map((n) => (n.id === id ? { ...n, leida: true } : n)),
      );
      setNoLeidas((prev) => Math.max(0, prev - 1));
      setTotal((prev) => (filtro === 'no-leidas' ? Math.max(0, prev - 1) : prev));
    } catch {
      // Reintento manual disponible
    }
  };

  const marcarTodas = async () => {
    try {
      await notificationService.markAllAsRead();
      if (filtro === 'no-leidas') {
        setItems([]);
        setTotal(0);
      } else {
        setItems((prev) => prev.map((n) => ({ ...n, leida: true })));
      }
      setNoLeidas(0);
    } catch {
      // Reintento manual disponible
    }
  };

  const resumen = useMemo(() => {
    if (loading) return 'Cargando avisos...';
    if (filtro === 'no-leidas') return `${total} notificación(es) sin leer`;
    return `${total} notificación(es), ${noLeidas} sin leer`;
  }, [loading, filtro, total, noLeidas]);

  return (
    <div className="animate-fade-in px-4 sm:px-8 lg:px-10 py-8 lg:py-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-6">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-text-main">Centro de avisos</h2>
          <p className="text-text-muted mt-1">{resumen}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void cargar('refresh')}
            disabled={loading || refreshing}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border-custom bg-surface text-sm font-medium text-text-main hover:bg-bg-secondary disabled:opacity-60"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} aria-hidden />
            Actualizar
          </button>
          {noLeidas > 0 && (
            <button
              type="button"
              onClick={() => void marcarTodas()}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-blue text-white text-sm font-medium hover:bg-primary-blue/90"
            >
              <CheckCheck className="w-4 h-4" aria-hidden />
              Marcar todas como leídas
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-5" role="tablist" aria-label="Filtro de notificaciones">
        <button
          type="button"
          role="tab"
          aria-selected={filtro === 'todas'}
          onClick={() => setFiltro('todas')}
          className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
            filtro === 'todas'
              ? 'bg-primary-blue text-white border-primary-blue'
              : 'bg-surface text-text-muted border-border-custom hover:text-text-main'
          }`}
        >
          Todas
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={filtro === 'no-leidas'}
          onClick={() => setFiltro('no-leidas')}
          className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
            filtro === 'no-leidas'
              ? 'bg-primary-blue text-white border-primary-blue'
              : 'bg-surface text-text-muted border-border-custom hover:text-text-main'
          }`}
        >
          No leídas {noLeidas > 0 ? `(${noLeidas})` : ''}
        </button>
      </div>

      {error && !loading && items.length > 0 && (
        <Alert tone="error" className="mb-4">
          {error}
        </Alert>
      )}

      {loading ? (
        <div className="rounded-xl border border-border-custom bg-surface p-8 flex justify-center" role="status">
          <LoadingState message="Cargando notificaciones..." />
        </div>
      ) : error && items.length === 0 ? (
        <ErrorState
          title="No se pudieron cargar los avisos"
          message={error}
          onRetry={() => void cargar('initial')}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Bell}
          title={filtro === 'no-leidas' ? 'No tienes avisos sin leer' : 'No hay notificaciones'}
          description={
            filtro === 'no-leidas'
              ? 'Cuando recibas nuevos avisos aparecerán aquí.'
              : 'Los avisos y notificaciones del sistema se mostrarán en este centro.'
          }
        />
      ) : (
        <ul className="space-y-3" aria-label="Lista de notificaciones">
          {items.map((n) => (
            <li
              key={n.id}
              className={`rounded-xl border p-4 sm:p-5 transition-colors ${
                n.leida
                  ? 'border-border-custom bg-surface'
                  : 'border-primary-blue/30 bg-primary-blue/5'
              }`}
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      {tipoLabel(n.tipo)}
                    </span>
                    {!n.leida && (
                      <span className="inline-flex items-center rounded-full bg-primary-orange/15 px-2 py-0.5 text-[11px] font-semibold text-primary-orange">
                        Nuevo
                      </span>
                    )}
                  </div>
                  <h3 className={`text-base ${n.leida ? 'font-medium text-text-main' : 'font-semibold text-text-main'}`}>
                    {n.titulo}
                  </h3>
                  <p className="text-sm text-text-muted mt-1 whitespace-pre-wrap break-words">{n.mensaje}</p>
                  <p className="text-xs text-text-muted mt-2">{formatFecha(n.creadaEn)}</p>
                </div>
                <div className="shrink-0">
                  {!n.leida && (
                    <button
                      type="button"
                      onClick={() => void marcarLeida(n.id)}
                      className="inline-flex items-center justify-center px-3 py-2 rounded-lg border border-border-custom bg-surface text-sm font-medium text-text-main hover:bg-bg-secondary w-full sm:w-auto"
                    >
                      Marcar como leída
                    </button>
                  )}
                </div>
              </div>
              <NotificationDeliveryPanel id={n.id} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
