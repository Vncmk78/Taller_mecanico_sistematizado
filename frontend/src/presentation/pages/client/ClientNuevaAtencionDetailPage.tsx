import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, FileQuestion } from 'lucide-react';
import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import { getApiErrorMessage, isNotFoundError } from '@/infrastructure/api/errors';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { SituacionSolicitudBadge } from '@/presentation/components/nuevaAtencion/SituacionSolicitudBadge';
import {
    RUTA_SOLICITUDES_CLIENTE,
    rutaOrdenDeSolicitud,
} from '@/presentation/components/nuevaAtencion/rutasNuevaAtencion';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { formatDateTime } from '@/presentation/utils/orderDisplay';

type Carga =
    | { estado: 'cargando' }
    | { estado: 'no_encontrada' }
    | { estado: 'error'; mensaje: string }
    | { estado: 'lista'; solicitud: SolicitudNuevaAtencion };

const volver = (
    <Link to={RUTA_SOLICITUDES_CLIENTE} className="text-primary-blue text-sm font-medium no-underline hover:underline">
        Volver a las solicitudes
    </Link>
);

/** Detalle de una solicitud de nueva atención con la respuesta administrativa. */
export function ClientNuevaAtencionDetailPage() {
    const { id } = useParams<{ id: string }>();
    const user = useAuthStore((s) => s.user);
    const vehicles = useVehicleStore((s) => s.vehicles);
    const [carga, setCarga] = useState<Carga>({ estado: 'cargando' });
    const [reintento, setReintento] = useState(0);

    useEffect(() => {
        if (!id) return;
        let activo = true;
        nuevaAtencionService
            .obtener(id)
            .then((solicitud) => {
                if (activo) setCarga({ estado: 'lista', solicitud });
            })
            .catch((err: unknown) => {
                if (!activo) return;
                setCarga(
                    isNotFoundError(err)
                        ? { estado: 'no_encontrada' }
                        : { estado: 'error', mensaje: getApiErrorMessage(err, 'No se pudo cargar la solicitud.') }
                );
            });
        return () => {
            activo = false;
        };
    }, [id, reintento]);

    if (carga.estado === 'cargando') {
        return <LoadingState message="Cargando solicitud..." className="p-4 sm:p-6 lg:p-10" />;
    }
    if (carga.estado === 'error') {
        return (
            <ErrorState
                className="p-4 sm:p-6 lg:p-10"
                title="No se pudo cargar la solicitud"
                message={carga.mensaje}
                onRetry={() => {
                    setCarga({ estado: 'cargando' });
                    setReintento((n) => n + 1);
                }}
                action={volver}
            />
        );
    }
    if (carga.estado === 'no_encontrada') {
        return (
            <EmptyState
                className="p-4 sm:p-6 lg:p-10"
                icon={FileQuestion}
                title="Solicitud no encontrada."
                description="Verifique el número o que la solicitud pertenezca a su cuenta."
                action={volver}
            />
        );
    }

    const s = carga.solicitud;
    const vehiculo = vehicles.find((v) => v.id === s.vehiculoId);
    const enlaceOrden = (ordenId: string) => rutaOrdenDeSolicitud(s, ordenId, user);

    return (
        <div className="animate-fade-in p-4 sm:p-6 lg:p-10">
            <Link
                to={RUTA_SOLICITUDES_CLIENTE}
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a las solicitudes
            </Link>

            <section className="card p-6" aria-labelledby="solicitud-titulo">
                <div className="flex justify-between items-center gap-3 mb-6 pb-4 border-b border-border-custom flex-wrap">
                    <h1 id="solicitud-titulo" className="text-xl font-semibold">
                        Solicitud de nueva atención n° {s.id}
                    </h1>
                    <SituacionSolicitudBadge situacion={s.situacion} />
                </div>

                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div>
                        <dt className="text-text-muted text-sm mb-1">Orden cancelada de referencia</dt>
                        <dd>
                            <Link to={enlaceOrden(s.ordenCanceladaId)} className="text-primary-blue font-medium no-underline hover:underline">
                                Orden n° {s.ordenCanceladaId}
                            </Link>
                        </dd>
                    </div>
                    <div>
                        <dt className="text-text-muted text-sm mb-1">Vehículo</dt>
                        <dd className="font-medium">
                            {vehiculo ? `${vehiculo.patent} · ${vehiculo.brand} ${vehiculo.model}` : `Vehículo N°${s.vehiculoId}`}
                        </dd>
                    </div>
                    <div>
                        <dt className="text-text-muted text-sm mb-1">Enviada el</dt>
                        <dd className="font-medium">{formatDateTime(s.solicitadaEn)}</dd>
                    </div>
                    <div className="sm:col-span-2">
                        <dt className="text-text-muted text-sm mb-1">Descripción</dt>
                        <dd className="whitespace-pre-line">{s.descripcion}</dd>
                    </div>
                </dl>
            </section>

            <section className="card p-6 mt-6" aria-labelledby="solicitud-revision">
                <h2 id="solicitud-revision" className="text-lg font-semibold mb-4">
                    Revisión del taller
                </h2>
                {s.situacion === 'pendiente' ? (
                    <p className="text-text-muted">
                        La solicitud está pendiente de revisión. No reserva una hora ni crea una orden.
                    </p>
                ) : (
                    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        <div className="sm:col-span-2">
                            <dt className="text-text-muted text-sm mb-1">Respuesta</dt>
                            <dd className="whitespace-pre-line">{s.respuesta ?? 'Sin respuesta registrada.'}</dd>
                        </div>
                        {s.revisadaEn && (
                            <div>
                                <dt className="text-text-muted text-sm mb-1">Revisada el</dt>
                                <dd className="font-medium">{formatDateTime(s.revisadaEn)}</dd>
                            </div>
                        )}
                        {s.revisorId && (
                            <div>
                                <dt className="text-text-muted text-sm mb-1">Revisada por (usuario)</dt>
                                <dd className="font-medium">{s.revisorId}</dd>
                            </div>
                        )}
                    </dl>
                )}

                {s.ordenGeneradaId ? (
                    <Alert tone="success" className="mt-6">
                        El taller generó la orden n° {s.ordenGeneradaId} a partir de esta solicitud.{' '}
                        <Link to={enlaceOrden(s.ordenGeneradaId)} className="underline">
                            Ver orden n° {s.ordenGeneradaId}
                        </Link>
                    </Alert>
                ) : s.situacion === 'aceptada' ? (
                    <p className="text-text-muted text-sm mt-6">Aún no hay una orden generada para esta solicitud.</p>
                ) : null}

                {s.situacion === 'rechazada' && (
                    <p className="text-text-muted text-sm mt-6">
                        Puede enviar una nueva solicitud desde la{' '}
                        <Link to={enlaceOrden(s.ordenCanceladaId)} className="text-primary-blue no-underline hover:underline">
                            orden cancelada n° {s.ordenCanceladaId}
                        </Link>
                        ; esta solicitud se conserva.
                    </p>
                )}
            </section>
        </div>
    );
}
