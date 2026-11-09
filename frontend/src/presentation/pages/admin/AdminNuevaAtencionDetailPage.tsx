import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, FileQuestion } from 'lucide-react';
import { GenerarOrdenSolicitudPanel } from '@/presentation/components/nuevaAtencion/GenerarOrdenSolicitudPanel';
import { RevisionSolicitudPanel } from '@/presentation/components/nuevaAtencion/RevisionSolicitudPanel';
import { SolicitudDetalle } from '@/presentation/components/nuevaAtencion/SolicitudDetalle';
import { RUTA_SOLICITUDES_ADMIN, rutaOrdenAdmin } from '@/presentation/components/nuevaAtencion/rutasNuevaAtencion';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { useSolicitudNuevaAtencion } from '@/presentation/hooks/useSolicitudNuevaAtencion';

const volver = (
    <Link to={RUTA_SOLICITUDES_ADMIN} className="text-primary-blue text-sm font-medium no-underline hover:underline">
        Volver a las solicitudes
    </Link>
);

/** Detalle administrativo: auditoría, revisión y generación de la orden. */
export function AdminNuevaAtencionDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { carga, recargar, reemplazar, comprobar } = useSolicitudNuevaAtencion(id);

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
                description="Verifique el número de la solicitud."
                action={volver}
            />
        );
    }

    const s = carga.solicitud;
    return (
        <div className="animate-fade-in p-4 sm:p-6 lg:p-10">
            <Link
                to={RUTA_SOLICITUDES_ADMIN}
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a las solicitudes
            </Link>

            <SolicitudDetalle solicitud={s} rutaOrden={rutaOrdenAdmin} mostrarCliente />

            <RevisionSolicitudPanel key={`revision-${s.id}`} solicitud={s} alRevisar={reemplazar} comprobar={comprobar} />
            <GenerarOrdenSolicitudPanel key={`orden-${s.id}`} solicitud={s} alGenerar={reemplazar} comprobar={comprobar} />
        </div>
    );
}
