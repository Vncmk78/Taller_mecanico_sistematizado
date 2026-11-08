import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import {
    SITUACIONES_SOLICITUD,
    type SituacionSolicitud,
    type SolicitudNuevaAtencion,
} from '@/domain/entities/SolicitudNuevaAtencion';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { SituacionSolicitudBadge } from '@/presentation/components/nuevaAtencion/SituacionSolicitudBadge';
import { RUTA_SOLICITUDES_CLIENTE } from '@/presentation/components/nuevaAtencion/rutasNuevaAtencion';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { Select } from '@/presentation/components/ui/Select';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { hasAnyRole } from '@/presentation/utils/roleVisibility';

export const SOLICITUDES_POR_PAGINA = 20;

/**
 * Listado de solicitudes de nueva atención (GET /api/ordenes/nuevas-atenciones).
 * El alcance lo decide MS2: un Cliente ve las propias y una cuenta que incluye
 * Administrador ve todas, por eso el encabezado lo indica en ese caso.
 */
export function ClientNuevasAtencionesPage() {
    const user = useAuthStore((s) => s.user);
    const alcanceAdministrativo = hasAnyRole(user, 'administrador');

    const [situacion, setSituacion] = useState<SituacionSolicitud | ''>('');
    const [offset, setOffset] = useState(0);
    const [items, setItems] = useState<SolicitudNuevaAtencion[]>([]);
    const [total, setTotal] = useState(0);
    const [cargando, setCargando] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reintento, setReintento] = useState(0);

    useEffect(() => {
        let activo = true;
        nuevaAtencionService
            .listar(situacion ? { situacion } : {}, { limit: SOLICITUDES_POR_PAGINA, offset })
            .then((pagina) => {
                if (!activo) return;
                setItems(pagina.items);
                setTotal(pagina.total);
                setError(null);
            })
            .catch((err: unknown) => {
                if (activo) setError(getApiErrorMessage(err, 'No se pudieron cargar las solicitudes.'));
            })
            .finally(() => {
                if (activo) setCargando(false);
            });
        return () => {
            activo = false;
        };
    }, [situacion, offset, reintento]);

    const recargar = (cambio: () => void) => {
        setCargando(true);
        cambio();
    };

    const desde = total === 0 ? 0 : offset + 1;
    const hasta = Math.min(offset + SOLICITUDES_POR_PAGINA, total);

    return (
        <div className="animate-fade-in p-4 sm:p-6 lg:p-10">
            <header className="mb-6">
                <h1 className="text-3xl font-bold flex items-center gap-3">
                    <RotateCcw className="w-7 h-7 text-text-muted" aria-hidden />
                    {alcanceAdministrativo ? 'Solicitudes de nueva atención' : 'Mis solicitudes de nueva atención'}
                </h1>
                <p className="text-text-muted mt-2">
                    {alcanceAdministrativo
                        ? 'Su cuenta incluye el rol Administrador: se muestran las solicitudes de todos los clientes.'
                        : 'Solicitudes enviadas después de una cancelación. Cada una queda pendiente hasta que el taller la revise.'}
                </p>
            </header>

            <Select
                id="filtro-situacion-solicitud"
                label="Situación"
                value={situacion}
                onChange={(e) =>
                    recargar(() => {
                        setSituacion(e.target.value as SituacionSolicitud | '');
                        setOffset(0);
                    })
                }
                containerClassName="mb-6 max-w-xs"
            >
                <option value="">Todas</option>
                {(Object.keys(SITUACIONES_SOLICITUD) as SituacionSolicitud[]).map((s) => (
                    <option key={s} value={s}>
                        {SITUACIONES_SOLICITUD[s]}
                    </option>
                ))}
            </Select>

            {cargando ? (
                <LoadingState message="Cargando solicitudes..." />
            ) : error ? (
                <Alert
                    tone="error"
                    action={<RetryButton tone="error" onClick={() => recargar(() => setReintento((n) => n + 1))} />}
                >
                    {error}
                </Alert>
            ) : total === 0 ? (
                <EmptyState
                    icon={RotateCcw}
                    title={situacion ? 'No hay solicitudes con esa situación.' : 'Aún no hay solicitudes de nueva atención.'}
                    description="Puede solicitar una nueva atención desde el detalle de una orden cancelada."
                    action={
                        <Link to="/client/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                            Ir a mis órdenes
                        </Link>
                    }
                />
            ) : (
                <>
                    <ul className="flex flex-col gap-3" aria-label="Solicitudes de nueva atención">
                        {items.map((s) => (
                            <li key={s.id}>
                                <Link
                                    to={`${RUTA_SOLICITUDES_CLIENTE}/${s.id}`}
                                    className="card p-4 flex items-start justify-between gap-3 no-underline hover:bg-bg-secondary transition-colors"
                                >
                                    <div className="min-w-0">
                                        <p className="text-text-main font-semibold">
                                            Solicitud n° {s.id} · orden cancelada n° {s.ordenCanceladaId}
                                        </p>
                                        <p className="text-text-muted text-sm">
                                            Enviada el {formatDateTime(s.solicitadaEn)}
                                            {s.ordenGeneradaId ? ` · generó la orden n° ${s.ordenGeneradaId}` : ''}
                                        </p>
                                        <p className="text-text-muted text-sm mt-1 line-clamp-2">{s.descripcion}</p>
                                    </div>
                                    <SituacionSolicitudBadge situacion={s.situacion} />
                                </Link>
                            </li>
                        ))}
                    </ul>

                    {total > SOLICITUDES_POR_PAGINA && (
                        <div className="mt-4 flex items-center justify-between gap-3">
                            <p className="text-text-muted text-sm" aria-live="polite">
                                {desde}–{hasta} de {total}
                            </p>
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    className="rounded-md border border-border-custom px-3 py-1.5 text-sm text-primary-blue disabled:cursor-not-allowed disabled:opacity-50"
                                    disabled={offset === 0}
                                    onClick={() =>
                                        recargar(() => setOffset((v) => Math.max(0, v - SOLICITUDES_POR_PAGINA)))
                                    }
                                >
                                    Anterior
                                </button>
                                <button
                                    type="button"
                                    className="rounded-md border border-border-custom px-3 py-1.5 text-sm text-primary-blue disabled:cursor-not-allowed disabled:opacity-50"
                                    disabled={offset + SOLICITUDES_POR_PAGINA >= total}
                                    onClick={() => recargar(() => setOffset((v) => v + SOLICITUDES_POR_PAGINA))}
                                >
                                    Siguiente
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
