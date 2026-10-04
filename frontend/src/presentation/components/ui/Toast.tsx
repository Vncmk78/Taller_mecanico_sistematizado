import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastTone = 'success' | 'error' | 'info';

export interface ToastMessage {
    id: number;
    tone: ToastTone;
    text: string;
}

interface ToastProps {
    toast: ToastMessage;
    onDismiss: (id: number) => void;
}

const AUTO_DISMISS_MS = 4000;

const toneClasses: Record<ToastTone, string> = {
    success: 'border-status-green bg-status-green/10 text-status-green',
    error: 'border-status-red bg-status-red/10 text-status-red',
    info: 'border-primary-blue bg-primary-blue/10 text-primary-blue',
};

const toneIcons: Record<ToastTone, typeof CheckCircle2> = {
    success: CheckCircle2,
    error: AlertCircle,
    info: Info,
};

/**
 * Aviso flotante de confirmación o error. Se monta en un portal del documento
 * para quedar por encima del layout y cierra solo tras unos segundos, además de
 * permitir el cierre manual con el botón y la tecla Escape.
 */
export function Toast({ toast, onDismiss }: ToastProps) {
    useEffect(() => {
        const timer = setTimeout(() => onDismiss(toast.id), AUTO_DISMISS_MS);
        return () => clearTimeout(timer);
    }, [toast.id, onDismiss]);

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') onDismiss(toast.id);
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [toast.id, onDismiss]);

    const Icon = toneIcons[toast.tone];

    return createPortal(
        <div
            role="status"
            aria-live="polite"
            className={`animate-fade-in flex items-start gap-3 w-full max-w-sm p-4 rounded-lg border border-solid shadow-lg ${toneClasses[toast.tone]}`}
        >
            <Icon className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
            <p className="flex-1 text-sm text-text-main break-words">{toast.text}</p>
            <button
                type="button"
                aria-label="Cerrar aviso"
                onClick={() => onDismiss(toast.id)}
                className="shrink-0 text-text-muted hover:text-text-main bg-transparent border-none cursor-pointer"
            >
                <X className="w-4 h-4" />
            </button>
        </div>,
        document.body
    );
}