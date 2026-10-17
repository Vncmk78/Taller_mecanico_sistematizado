import { RefreshCw } from 'lucide-react';

interface RetryButtonProps {
    onClick: () => void;
    label?: string;
    /** 'warning' para banners de sin conexión, 'error' para errores del servidor. */
    tone?: 'warning' | 'error';
    className?: string;
}

const toneClasses = {
    warning:
        'text-primary-blue bg-status-yellow/10 hover:bg-status-yellow/20 border-status-yellow/40 hover:border-status-yellow/60',
    error: 'text-primary-blue bg-status-red/10 hover:bg-status-red/20 border-status-red/40 hover:border-status-red/60',
};

/** Botón de reintento compartido por el banner offline, los estados de error y los alerts. */
export function RetryButton({ onClick, label = 'Reintentar', tone = 'error', className = '' }: RetryButtonProps) {
    return (
        <button
            type="button"
            onClick={onClick}
            className={`flex items-center gap-1.5 shrink-0 rounded-md border px-3 py-1.5 transition-colors ${toneClasses[tone]} ${className}`}
        >
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
            {label}
        </button>
    );
}
