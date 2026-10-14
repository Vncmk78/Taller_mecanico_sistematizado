import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Alert } from '@/presentation/components/ui/Alert';
import { useDialogFocus } from '@/presentation/hooks/useDialogFocus';

interface RejectBudgetDialogProps {
    /** true cuando rechazar cancelará el servicio (antes de la primera aprobación). */
    cancelaServicio: boolean;
    isLoading?: boolean;
    /** Error del servidor al intentar rechazar. */
    error?: string | null;
    onConfirm: (motivo: string, confirmarCancelacion: boolean) => void;
    onCancel: () => void;
}

/**
 * Confirmación de rechazo de presupuesto. Se monta solo cuando está abierto (el
 * padre lo renderiza condicionalmente), de modo que el motivo y la confirmación
 * parten siempre en blanco. MS3 exige un motivo en todo rechazo y, antes de la
 * primera aprobación, la confirmación explícita de que el servicio se cancelará.
 */
const MOTIVO_MIN = 5;
const MOTIVO_MAX = 1000;

export function RejectBudgetDialog({
    cancelaServicio,
    isLoading = false,
    error = null,
    onConfirm,
    onCancel,
}: RejectBudgetDialogProps) {
    const [motivo, setMotivo] = useState('');
    const [confirmarCancelacion, setConfirmarCancelacion] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);
    const { ref: dialogRef, handleKeyDown: handleDialogKeyDown } = useDialogFocus<HTMLDivElement>();

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && !isLoading) onCancel();
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [isLoading, onCancel]);

    const handleConfirm = () => {
        const limpio = motivo.trim();
        if (!limpio) {
            setLocalError('Indique el motivo del rechazo.');
            return;
        }
        if (limpio.length < MOTIVO_MIN) {
            setLocalError(`Describa el motivo con al menos ${MOTIVO_MIN} caracteres.`);
            return;
        }
        if (cancelaServicio && !confirmarCancelacion) {
            setLocalError('Debe confirmar que desea cancelar el servicio.');
            return;
        }
        setLocalError(null);
        onConfirm(limpio, confirmarCancelacion);
    };

    return (
        <div
            className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 animate-fade-in"
            onMouseDown={(e) => {
                if (e.target === e.currentTarget && !isLoading) onCancel();
            }}
        >
            <div
                ref={dialogRef}
                role="dialog"
                aria-modal="true"
                aria-label="Rechazar presupuesto"
                tabIndex={-1}
                onKeyDown={handleDialogKeyDown}
                className="card relative w-full max-w-[480px] p-8 outline-none"
            >
                <button
                    type="button"
                    aria-label="Cerrar"
                    onClick={onCancel}
                    disabled={isLoading}
                    className="absolute right-4 top-4 text-text-muted hover:text-text-main bg-transparent border-none cursor-pointer disabled:opacity-50"
                >
                    <X className="w-5 h-5" aria-hidden />
                </button>

                <h3 className="text-2xl font-bold tracking-tight text-text-main">Rechazar presupuesto</h3>
                <p className="mt-2 text-text-muted text-sm">
                    Cuéntenos por qué rechaza este presupuesto. El taller revisará su comentario.
                </p>

                <label htmlFor="motivo-rechazo" className="block mt-5 mb-2 text-sm text-text-muted">
                    Motivo del rechazo
                </label>
                <textarea
                    id="motivo-rechazo"
                    value={motivo}
                    onChange={(event) => setMotivo(event.target.value)}
                    maxLength={MOTIVO_MAX}
                    rows={4}
                    disabled={isLoading}
                    className="w-full py-3 px-4 bg-surface border border-border-custom rounded-lg text-text-main text-base outline-none focus:border-primary-blue focus:shadow-[0_0_0_3px_rgba(21,40,63,0.15)] resize-none disabled:opacity-50"
                    placeholder="Ej: El costo me parece elevado / prefiero una segunda opinión."
                />
                <div className="flex justify-between text-xs text-text-muted mt-1">
                    <span>Mínimo {MOTIVO_MIN} caracteres.</span>
                    <span aria-live="polite">
                        {motivo.length}/{MOTIVO_MAX}
                    </span>
                </div>

                {cancelaServicio && (
                    <label className="flex items-start gap-3 mt-4 text-sm text-text-main cursor-pointer">
                        <input
                            type="checkbox"
                            checked={confirmarCancelacion}
                            onChange={(event) => setConfirmarCancelacion(event.target.checked)}
                            disabled={isLoading}
                            className="mt-0.5 accent-status-red"
                        />
                        <span>
                            Entiendo que, al rechazar antes de aprobar, se cancelará este servicio.
                        </span>
                    </label>
                )}

                {(localError || error) && (
                    <Alert tone="error" className="mt-4">
                        {localError ?? error}
                    </Alert>
                )}

                <div className="flex flex-col sm:flex-row sm:items-center justify-end gap-3 mt-8">
                    <Button type="button" variant="secondary" disabled={isLoading} onClick={onCancel} className="sm:flex-1 py-3">
                        Cancelar
                    </Button>
                    <Button type="button" variant="danger" isLoading={isLoading} onClick={handleConfirm} className="sm:flex-1 py-3">
                        Rechazar presupuesto
                    </Button>
                </div>
            </div>
        </div>
    );
}
