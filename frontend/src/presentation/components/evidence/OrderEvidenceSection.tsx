import { Images } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { Spinner } from '@/presentation/components/ui/Spinner';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { useOrderEvidence } from '@/presentation/hooks/useOrderEvidence';
import { EvidenceGallery } from './EvidenceGallery';
import { EvidenceUploadForm } from './EvidenceUploadForm';

interface OrderEvidenceSectionProps {
    orderId: string;
    /** El rol actual puede subir evidencia (Mecánico/Administrador). */
    canUpload?: boolean;
    /** Enlace opcional a la vista dedicada de evidencias. */
    moreHref?: string;
    className?: string;
}

/**
 * Evidencia multimedia de una orden para el personal: permite subir fotos y
 * videos (con progreso y confirmación) y lista las ya cargadas. El listado
 * reutiliza el mismo manejo de estados (carga, vacío, offline y error) que el
 * resto del portal.
 */
export function OrderEvidenceSection({ orderId, canUpload = false, moreHref, className = '' }: OrderEvidenceSectionProps) {
    const { evidencias, loading, notFound, error, isOffline, requestId, refetch } = useOrderEvidence(orderId);

    return (
        <section className={`card p-6 ${className}`} aria-labelledby="order-evidence-title">
            <div className="mb-6 flex items-center justify-between gap-4">
                <h3 id="order-evidence-title" className="flex items-center gap-2 text-xl font-semibold">
                    <Images className="h-5 w-5 text-text-muted" aria-hidden />
                    Evidencias
                </h3>
                {moreHref && (
                    <Link
                        to={moreHref}
                        className="text-sm font-medium text-primary-blue no-underline hover:underline"
                    >
                        Ver todas
                    </Link>
                )}
            </div>

            {isOffline && (
                <OfflineBanner message={error} onRetry={refetch} requestId={requestId} className="mb-6" />
            )}
            {!isOffline && error && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={refetch} />}>
                    {error} Se muestran las últimas evidencias disponibles.
                    {requestId && (
                        <span className="block mt-1 font-mono text-xs opacity-80">Referencia: {requestId}</span>
                    )}
                </Alert>
            )}

            {canUpload && (
                <EvidenceUploadForm
                    orderId={orderId}
                    className={evidencias.length > 0 || loading ? 'mb-6 border-b border-border-custom pb-6' : ''}
                />
            )}

            {notFound ? (
                <EmptyState
                    icon={Images}
                    title="Orden no encontrada."
                    description="Verifique el número de orden o que siga disponible para su cuenta."
                />
            ) : loading ? (
                <div className="flex items-center gap-2 text-text-muted">
                    <Spinner className="h-5 w-5" /> Cargando evidencias...
                </div>
            ) : evidencias.length === 0 ? (
                <EmptyState
                    icon={Images}
                    title="Aún no hay evidencia multimedia"
                    description={
                        canUpload
                            ? 'Sube una foto o un video del diagnóstico, la reparación o el resultado final.'
                            : 'Cuando se registren fotos o videos de esta orden aparecerán aquí.'
                    }
                />
            ) : (
                <EvidenceGallery evidencias={evidencias} />
            )}
        </section>
    );
}