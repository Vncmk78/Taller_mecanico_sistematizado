import { AlertTriangle, RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';

interface ErrorStateProps {
    title: string;
    /** Mensaje normalizado del store (getApiErrorMessage). */
    message?: string | null;
    onRetry?: () => void;
    retryLabel?: string;
    /** Acción secundaria (volver al listado, por ejemplo). */
    action?: ReactNode;
    /** X-Request-ID de la Gateway, para rastrear el fallo en los logs del backend. */
    requestId?: string | null;
    className?: string;
}

/**
 * Estado de error reutilizable para cuando no hay nada que mostrar porque el
 * fetch falló. Es el contraparte de OfflineBanner: este último solo aparece
 * cuando la Gateway no respondió, no ante errores del servidor.
 */
export function ErrorState({
    title,
    message,
    onRetry,
    retryLabel = 'Reintentar',
    action,
    requestId,
    className = '',
}: ErrorStateProps) {
    return (
        <div
            role="alert"
            className={`col-span-full flex flex-col items-center justify-center text-center py-12 px-6 ${className}`}
        >
            <span className="flex items-center justify-center w-14 h-14 rounded-full bg-status-red/10 text-status-red mb-4">
                <AlertTriangle className="w-6 h-6" aria-hidden="true" />
            </span>
            <p className="font-semibold">{title}</p>
            {message && <p className="text-text-muted text-sm mt-1 max-w-md">{message}</p>}
            {requestId && (
                <p className="text-text-muted text-xs mt-2 font-mono max-w-md break-all">
                    Referencia: {requestId}
                </p>
            )}
            {(onRetry || action) && (
                <div className="mt-4 flex items-center gap-3 flex-wrap justify-center">
                    {onRetry && (
                        <button
                            type="button"
                            onClick={onRetry}
                            className="inline-flex items-center gap-2 bg-primary-blue text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-blue-hover transition-colors"
                        >
                            <RefreshCw className="w-4 h-4" aria-hidden="true" />
                            {retryLabel}
                        </button>
                    )}
                    {action}
                </div>
            )}
        </div>
    );
}
