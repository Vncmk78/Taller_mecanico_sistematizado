import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { SituacionSolicitudBadge } from './SituacionSolicitudBadge';

interface SolicitudDetalleProps {
    solicitud: SolicitudNuevaAtencion;
    /** Ruta del detalle de una orden (antecedente o generada) en el portal actual. */
    rutaOrden: (ordenId: string) => string;
    /** Muestra el usuario Cliente que envió la solicitud (portal administrativo). */
    mostrarCliente?: boolean;
    /** Contenido adicional al final de la revisión (p. ej. cómo volver a solicitar). */
    pieRevision?: ReactNode;
}

/**
 * Datos de una solicitud de nueva atención y la auditoría de su revisión tal
 * como las registra el servidor: situación, respuesta, responsable, fecha y
 * orden generada. Compartido por los portales Cliente y Administrador.
 */
export function SolicitudDetalle({ solicitud: s, rutaOrden, mostrarCliente = false, pieRevision }: SolicitudDetalleProps) {
    const vehicles = useVehicleStore((st) => st.vehicles);
    const vehiculo = vehicles.find((v) => v.id === s.vehiculoId);

    return (
        <>
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
                            <Link to={rutaOrden(s.ordenCanceladaId)} className="text-primary-blue font-medium no-underline hover:underline">
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
                    {mostrarCliente && (
                        <div>
                            <dt className="text-text-muted text-sm mb-1">Cliente (usuario)</dt>
                            <dd className="font-medium">{s.clienteUsuarioId}</dd>
                        </div>
                    )}
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
                        <Link to={rutaOrden(s.ordenGeneradaId)} className="underline">
                            Ver orden n° {s.ordenGeneradaId}
                        </Link>
                    </Alert>
                ) : s.situacion === 'aceptada' ? (
                    <p className="text-text-muted text-sm mt-6">Aún no hay una orden generada para esta solicitud.</p>
                ) : null}

                {pieRevision}
            </section>
        </>
    );
}
