import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import {
    SITUACIONES_SOLICITUD,
    type FiltrosSolicitudes,
    type SituacionSolicitud,
    type SolicitudNuevaAtencion,
} from '@/domain/entities/SolicitudNuevaAtencion';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { Input } from '@/presentation/components/ui/Input';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { Select } from '@/presentation/components/ui/Select';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { SituacionSolicitudBadge } from './SituacionSolicitudBadge';

export const SOLICITUDES_POR_PAGINA = 20;

interface ListadoSolicitudesProps {
    /** Ruta del detalle de una solicitud en el portal actual. */
    rutaDetalle: (solicitudId: string) => string;
    /** Agrega los filtros por orden cancelada y orden generada (portal administrativo). */
    filtrosPorOrden?: boolean;
    /** Muestra el usuario Cliente de cada solicitud (alcance administrativo). */
    mostrarCliente?: boolean;
    /** Texto y acción de la lista vacía sin filtros. */
    vacio: { descripcion: string; accion?: ReactNode };
}

const ENTERO_POSITIVO = /^[1-9]\d*$/;

/**
 * Listado paginado en el servidor de GET /api/ordenes/nuevas-atenciones,
 * compartido por los portales Cliente y Administrador. El alcance (propias o
 * todas) lo decide MS2 según los roles de la cuenta.
 */
export function ListadoSolicitudes({
    rutaDetalle,
    filtrosPorOrden = false,
    mostrarCliente = false,
    vacio,
}: ListadoSolicitudesProps) {
    const [filtros, setFiltros] = useState<FiltrosSolicitudes>({});
    const [offset, setOffset] = useState(0);
    const [items, setItems] = useState<SolicitudNuevaAtencion[]>([]);
    const [total, setTotal] = useState(0);
    const [cargando, setCargando] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reintento, setReintento] = useState(0);

    const [ordenCancelada, setOrdenCancelada] = useState('');
    const [ordenGenerada, setOrdenGenerada] = useState('');
    const [errorFiltro, setErrorFiltro] = useState<string | null>(null);

    useEffect(() => {
        let activo = true;
        nuevaAtencionService
            .listar(filtros, { limit: SOLICITUDES_POR_PAGINA, offset })
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
    }, [filtros, offset, reintento]);

    const recargar = (cambio: () => void) => {
        setCargando(true);
        cambio();
    };

    const aplicarFiltros = (nuevos: FiltrosSolicitudes) =>
        recargar(() => {
            setFiltros(nuevos);
            setOffset(0);
        });

    const aplicarFiltrosPorOrden = (event: FormEvent) => {
        event.preventDefault();
        const cancelada = ordenCancelada.trim();
        const generada = ordenGenerada.trim();
        if ((cancelada && !ENTERO_POSITIVO.test(cancelada)) || (generada && !ENTERO_POSITIVO.test(generada))) {
            setErrorFiltro('Los números de orden deben ser enteros positivos.');
            return;
        }
        setErrorFiltro(null);
        aplicarFiltros({
            ...(filtros.situacion ? { situacion: filtros.situacion } : {}),
            ...(cancelada ? { ordenCanceladaId: cancelada } : {}),
            ...(generada ? { ordenGeneradaId: generada } : {}),
        });
    };

    const hayFiltros = Boolean(filtros.situacion || filtros.ordenCanceladaId || filtros.ordenGeneradaId);
    const desde = total === 0 ? 0 : offset + 1;
    const hasta = Math.min(offset + SOLICITUDES_POR_PAGINA, total);

    return (
        <>
            <div className="flex flex-wrap items-end gap-4 mb-6">
                <Select
                    id="filtro-situacion-solicitud"
                    label="Situación"
                    value={filtros.situacion ?? ''}
                    onChange={(e) => {
                        const situacion = e.target.value as SituacionSolicitud | '';
                        const resto: FiltrosSolicitudes = { ...filtros };
                        delete resto.situacion;
                        aplicarFiltros(situacion ? { ...resto, situacion } : resto);
                    }}
                    containerClassName="mb-0 min-w-[14rem]"
                >
                    <option value="">Todas</option>
                    {(Object.keys(SITUACIONES_SOLICITUD) as SituacionSolicitud[]).map((s) => (
                        <option key={s} value={s}>
                            {SITUACIONES_SOLICITUD[s]}
                        </option>
                    ))}
                </Select>

                {filtrosPorOrden && (
                    <form
                        onSubmit={aplicarFiltrosPorOrden}
                        noValidate
                        className="flex flex-wrap items-end gap-3"
                        aria-label="Filtrar por orden"
                    >
                        <Input
                            id="filtro-orden-cancelada"
                            label="Orden cancelada n°"
                            inputMode="numeric"
                            value={ordenCancelada}
                            onChange={(e) => setOrdenCancelada(e.target.value)}
                            containerClassName="mb-0 w-40"
                        />
                        <Input
                            id="filtro-orden-generada"
                            label="Orden generada n°"
                            inputMode="numeric"
                            value={ordenGenerada}
                            onChange={(e) => setOrdenGenerada(e.target.value)}
                            containerClassName="mb-0 w-40"
                        />
                        <Button type="submit" variant="secondary" className="px-4 py-3 text-sm">
                            Filtrar
                        </Button>
                    </form>
                )}
            </div>

            {errorFiltro && (
                <Alert tone="error" className="mb-4">
                    {errorFiltro}
                </Alert>
            )}

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
                    title={hayFiltros ? 'No hay solicitudes con esos filtros.' : 'Aún no hay solicitudes de nueva atención.'}
                    description={hayFiltros ? undefined : vacio.descripcion}
                    action={hayFiltros ? undefined : vacio.accion}
                />
            ) : (
                <>
                    <ul className="flex flex-col gap-3" aria-label="Solicitudes de nueva atención">
                        {items.map((s) => (
                            <li key={s.id}>
                                <Link
                                    to={rutaDetalle(s.id)}
                                    className="card p-4 flex items-start justify-between gap-3 no-underline hover:bg-bg-secondary transition-colors"
                                >
                                    <div className="min-w-0">
                                        <p className="text-text-main font-semibold">
                                            Solicitud n° {s.id} · orden cancelada n° {s.ordenCanceladaId}
                                        </p>
                                        <p className="text-text-muted text-sm">
                                            Enviada el {formatDateTime(s.solicitadaEn)}
                                            {mostrarCliente ? ` · cliente (usuario) n° ${s.clienteUsuarioId}` : ''}
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
        </>
    );
}
