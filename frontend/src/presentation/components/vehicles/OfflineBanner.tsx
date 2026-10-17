import { Alert } from '@/presentation/components/ui/Alert';
import { RetryButton } from '@/presentation/components/ui/RetryButton';

interface OfflineBannerProps {
    message: string | null;
    onRetry: () => void;
    /** X-Request-ID de la Gateway, para rastrear el fallo en los logs del backend. */
    requestId?: string | null;
    className?: string;
}

/**
 * Aviso de fallo de transporte: la Gateway no respondió o el servicio no estaba
 * disponible, por lo que se conserva la caché local. Los errores HTTP del
 * servidor se muestran con Alert/ErrorState, no con este banner.
 */
export function OfflineBanner({ message, onRetry, requestId, className = '' }: OfflineBannerProps) {
    return (
        <Alert
            tone="warning"
            className={className}
            action={<RetryButton tone="warning" onClick={onRetry} />}
        >
            {message ?? 'No se pudo conectar con el servidor.'} Mostrando datos disponibles localmente.
            {requestId && (
                <span className="block mt-1 font-mono text-xs opacity-80">Referencia: {requestId}</span>
            )}
        </Alert>
    );
}
