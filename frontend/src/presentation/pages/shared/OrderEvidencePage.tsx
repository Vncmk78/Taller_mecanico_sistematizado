import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Images } from 'lucide-react';
import { Alert } from '@/presentation/components/ui/Alert';
import { OrderEvidenceSection } from '@/presentation/components/evidence/OrderEvidenceSection';

interface OrderEvidencePageProps {
    /** Ruta de regreso del portal (p. ej. `/mechanic/ordenes`). */
    backTo: string;
    backLabel: string;
    /** El rol actual puede subir evidencia (Mecánico/Administrador). */
    canUpload?: boolean;
}

/**
 * Vista dedicada de evidencia multimedia de una orden para el personal
 * (Mecánico/Administrador): sube fotos y videos con progreso y confirmación, y
 * lista las ya cargadas. Reutiliza la misma sección que el detalle de la orden.
 */
export function OrderEvidencePage({ backTo, backLabel, canUpload = false }: OrderEvidencePageProps) {
    const { id } = useParams<{ id: string }>();

    return (
        <div className="animate-fade-in p-10">
            <Link
                to={backTo}
                className="mb-6 inline-flex items-center gap-2 text-text-muted no-underline hover:text-primary-blue"
            >
                <ArrowLeft className="h-4 w-4" aria-hidden /> {backLabel}
            </Link>

            <div className="mb-6">
                <h1 className="mb-1 flex items-center gap-3 text-3xl font-bold">
                    <Images className="h-6 w-6 text-text-muted" aria-hidden />
                    Evidencia multimedia
                </h1>
                <p className="text-text-muted">Orden de trabajo n° {id}</p>
            </div>

            <Alert tone="info" className="mb-8">
                Sube fotos o videos del diagnóstico, la reparación o el resultado final. Marca si la
                evidencia debe ser visible para el cliente.
            </Alert>

            <OrderEvidenceSection orderId={id ?? ''} canUpload={canUpload} />
        </div>
    );
}