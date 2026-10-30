import { useEffect, useId, useState } from 'react';
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
    const [localError, setLocalError] = useState<{
        campo: 'motivo' | 'confirmacion';
        mensaje: string;
    } | null>(null);
    const { ref: dialogRef, handleKeyDown: handleDialogKeyDown } = useDialogFocus<HTMLDivElement>();
    const titleId = useId();
    const descriptionId = useId();

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
            setLocalError({
                campo: 'motivo',
                mensaje: 'Indique el motivo del rechazo.',
            });
            return;
        }
        if (limpio.length < MOTIVO_MIN) {
            setLocalError({
                campo: 'motivo',
                mensaje: `Describa el motivo con al menos ${MOTIVO_MIN} caracteres.`,
            });
            return;
        }
        if (cancelaServicio && !confirmarCancelacion) {
            setLocalError({
                campo: 'confirmacion',
                mensaje: 'Debe confirmar que desea cancelar el servicio.',
            });
            return;
        }
        setLocalError(null);
        onConfirm(limpio, confirmarCancelacion);
    };

    const errorId =
        localError?.campo === 'motivo'
            ? 'motivo-rechazo-error'
            : localError?.campo === 'confirmacion'
              ? 'confirmacion-cancelacion-error'
              : undefined;
    const errorDelMotivo = localError?.campo === 'motivo';
    const errorDeConfirmacion = localError?.campo === 'confirmacion';

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
                aria-labelledby={titleId}
                aria-describedby={descriptionId}
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

                <h3 id={titleId} className="text-2xl font-bold tracking-tight text-text-main">
                    Rechazar presupuesto
                </h3>
                <p id={descriptionId} className="mt-2 text-text-muted text-sm">
                    Cuéntenos por qué rechaza este presupuesto. El taller revisará su comentario.
                </p>

                <label htmlFor="motivo-rechazo" className="block mt-5 mb-2 text-sm text-text-muted">
                    Motivo del rechazo
                </label>
                <textarea
                    id="motivo-rechazo"
                    name="motivo"
                    value={motivo}
                    onChange={(event) => {
                        setMotivo(event.target.value);
                        if (errorDelMotivo) setLocalError(null);
                    }}
                    maxLength={MOTIVO_MAX}
                    rows={4}
                    disabled={isLoading}
                    aria-required="true"
                    aria-invalid={errorDelMotivo ? true : undefined}
                    aria-describedby={[
                        'motivo-rechazo-hint',
                        'motivo-rechazo-contador',
                        errorDelMotivo ? 'motivo-rechazo-error' : null,
                    ]
                        .filter(Boolean)
                        .join(' ')}
                    className="w-full py-3 px-4 bg-surface border border-border-custom rounded-lg text-text-main text-base outline-none focus:border-primary-blue focus:shadow-[0_0_0_3px_rgba(21,40,63,0.15)] resize-none disabled:opacity-50"
                    placeholder="Ej: El costo me parece elevado / prefiero una segunda opinión."
                />
                <div className="flex justify-between text-xs text-text-muted mt-1">
                    <span id="motivo-rechazo-hint">Mínimo {MOTIVO_MIN} caracteres.</span>
                    <span id="motivo-rechazo-contador" aria-live="polite">
                        {motivo.length}/{MOTIVO_MAX}
                    </span>
                </div>

                {cancelaServicio && (
                    <label className="flex items-start gap-3 mt-4 text-sm text-text-main cursor-pointer">
                        <input
                            id="confirmar-cancelacion"
                            type="checkbox"
                            name="confirmar-cancelacion"
                            checked={confirmarCancelacion}
                            onChange={(event) => {
                                setConfirmarCancelacion(event.target.checked);
                                if (errorDeConfirmacion) setLocalError(null);
                            }}
                            disabled={isLoading}
                            aria-invalid={errorDeConfirmacion ? true : undefined}
                            aria-describedby={
                                errorDeConfirmacion
                                    ? 'confirmacion-cancelacion-error'
                                    : undefined
                            }
                            className="mt-0.5 accent-status-red"
                        />
                        <span>
                            Entiendo que, al rechazar antes de aprobar, se cancelará este servicio.
                        </span>
                    </label>
                )}

                {(localError || error) && (
                    <Alert tone="error" className="mt-4" id={errorId}>
                        {localError?.mensaje ?? error}
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
