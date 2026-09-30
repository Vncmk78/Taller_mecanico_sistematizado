import { RefreshCw, WifiOff } from 'lucide-react';

interface OfflineBannerProps {
    message: string | null;
    onRetry: () => void;
    className?: string;
}

export function OfflineBanner({ message, onRetry, className = '' }: OfflineBannerProps) {
    return (
    <div
        className={`flex items-center justify-between gap-3 flex-wrap text-status-yellow text-sm bg-status-yellow/10 border border-status-yellow/40 rounded-lg px-4 py-3 ${className}`}
    >
        <span className="flex items-center gap-2">
        <WifiOff className="w-4 h-4 shrink-0" />
        {message ?? 'No se pudo conectar con el servidor.'} Mostrando datos disponibles localmente.
        </span>
        <button
        onClick={onRetry}
        className="flex items-center gap-1.5 shrink-0 text-primary-blue bg-status-yellow/10 hover:bg-status-yellow/20 transition-colors rounded-md border border-status-yellow/40 hover:border-status-yellow/60 px-3 py-1.5"
        >
        <RefreshCw className="w-3.5 h-3.5" /> Reintentar
        </button>
    </div>
    );
}