import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ImageOff, Images } from 'lucide-react';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useOrderEvidence } from '@/presentation/hooks/useOrderEvidence';
import { EvidenceGallery } from '@/presentation/components/evidence/EvidenceGallery';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';

/**
 * Evidencia multimedia de una orden para el portal del cliente. Solo se listan
 * las fotos y videos que el taller marcó como visibles para el cliente; el
 * archivo se ve o se baja con una URL prefirmada efímera.
 */
export function ClientOrderEvidencePage() {
    const { id } = useParams<{ id: string }>();
    const { evidencias, loading, notFound, failed, error, isOffline, requestId, refetch } =
        useOrderEvidence(id);
    const order = useOrderStore((s) => s.orders.find((cached) => cached.id === id));

    if (loading) {
        return <LoadingState message="Cargando evidencia multimedia..." className="p-10" />;
    }

    if (failed) {
        return (
            <ErrorState
                className="p-10"
                title="No se pudo cargar la evidencia"
                message={error}
                requestId={requestId}
                onRetry={refetch}
                action={
                    <Link
                        to="/client/servicios"
                        className="text-primary-blue text-sm font-medium no-underline hover:underline"
                    >
                        Volver a mis servicios
                    </Link>
                }
            />
        );
    }

    if (notFound) {
        return (
            <EmptyState
                className="p-10"
                icon={ImageOff}
                title="Servicio no encontrado."
                description="Es posible que este servicio no exista o no pertenezca a su cuenta."
                action={
                    <Link
                        to="/client/servicios"
                        className="text-primary-blue text-sm font-medium no-underline hover:underline"
                    >
                        Volver a mis servicios
                    </Link>
                }
            />
        );
    }

    return (
        <div className="p-5 sm:p-8 lg:p-10 animate-fade-in">
            <Link
                to={`/client/ordenes/${id}`}
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver al detalle del servicio
            </Link>

            {isOffline && (
                <OfflineBanner message={error} onRetry={refetch} requestId={requestId} className="mb-6" />
            )}

            <div className="mb-6">
                <h2 className="text-3xl font-bold mb-1 flex items-center gap-3">
                    <Images className="w-6 h-6 text-text-muted" aria-hidden />
                    Evidencia multimedia
                </h2>
                <p className="text-text-muted">
                    Servicio n° {id}
                    {order ? ` · ${order.vehiculo ?? `Vehículo N°${order.vehicleId}`}` : ''}
                </p>
            </div>

            <Alert tone="info" className="mb-8">
                Fotos y videos del servicio autorizados para su revisión. El archivo se abre con un enlace
                temporal; si falla, vuelva a intentarlo.
            </Alert>

            {evidencias.length === 0 ? (
                <EmptyState
                    icon={Images}
                    title="Aún no hay evidencia multimedia"
                    description="Cuando el taller registre fotos o videos visibles para usted, aparecerán en esta sección."
                />
            ) : (
                <EvidenceGallery evidencias={evidencias} />
            )}
        </div>
    );
}
