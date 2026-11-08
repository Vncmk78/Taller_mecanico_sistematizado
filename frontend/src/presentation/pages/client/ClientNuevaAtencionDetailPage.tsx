import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, FileQuestion } from 'lucide-react';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { SolicitudDetalle } from '@/presentation/components/nuevaAtencion/SolicitudDetalle';
import {
    RUTA_SOLICITUDES_CLIENTE,
    rutaOrdenDeSolicitud,
} from '@/presentation/components/nuevaAtencion/rutasNuevaAtencion';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { useSolicitudNuevaAtencion } from '@/presentation/hooks/useSolicitudNuevaAtencion';

const volver = (
    <Link to={RUTA_SOLICITUDES_CLIENTE} className="text-primary-blue text-sm font-medium no-underline hover:underline">
        Volver a las solicitudes
    </Link>
);

/** Detalle de una solicitud de nueva atención con la respuesta administrativa (portal Cliente). */
export function ClientNuevaAtencionDetailPage() {
    const { id } = useParams<{ id: string }>();
    const user = useAuthStore((s) => s.user);
    const { carga, recargar } = useSolicitudNuevaAtencion(id);

    if (carga.estado === 'cargando') {
        return <LoadingState message="Cargando solicitud..." className="p-4 sm:p-6 lg:p-10" />;
    }
    if (carga.estado === 'error') {
        return (
            <ErrorState
                className="p-4 sm:p-6 lg:p-10"
                title="No se pudo cargar la solicitud"
                message={carga.mensaje}
                onRetry={recargar}
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
    const enlaceOrden = (ordenId: string) => rutaOrdenDeSolicitud(s, ordenId, user);

    return (
        <div className="animate-fade-in p-4 sm:p-6 lg:p-10">
            <Link
                to={RUTA_SOLICITUDES_CLIENTE}
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a las solicitudes
            </Link>

            <SolicitudDetalle
                solicitud={s}
                rutaOrden={enlaceOrden}
                pieRevision={
                    s.situacion === 'rechazada' ? (
                        <p className="text-text-muted text-sm mt-6">
                            Puede enviar una nueva solicitud desde la{' '}
                            <Link to={enlaceOrden(s.ordenCanceladaId)} className="text-primary-blue no-underline hover:underline">
                                orden cancelada n° {s.ordenCanceladaId}
                            </Link>
                            ; esta solicitud se conserva.
                        </p>
                    ) : undefined
                }
            />
        </div>
    );
}
