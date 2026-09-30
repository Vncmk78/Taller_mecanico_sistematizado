import { RefreshCw } from 'lucide-react';
import { Alert } from '@/presentation/components/ui/Alert';

interface OfflineBannerProps {
    message: string | null;
    onRetry: () => void;
    className?: string;
}

export function OfflineBanner({ message, onRetry, className = '' }: OfflineBannerProps) {
    return (
    <Alert
        tone="warning"
        className={className}
        action={
        <button
            onClick={onRetry}
            className="flex items-center gap-1.5 shrink-0 text-primary-blue bg-status-yellow/10 hover:bg-status-yellow/20 transition-colors rounded-md border border-status-yellow/40 hover:border-status-yellow/60 px-3 py-1.5"
        >
            <RefreshCw className="w-3.5 h-3.5" /> Reintentar
        </button>
        }
    >
        {message ?? 'No se pudo conectar con el servidor.'} Mostrando datos disponibles localmente.
    </Alert>
    );
}