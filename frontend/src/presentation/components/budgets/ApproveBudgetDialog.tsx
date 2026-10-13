import { useEffect, useState } from 'react';
import { CheckCircle2, X } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Alert } from '@/presentation/components/ui/Alert';
import { formatMoneyCLP } from '@/presentation/utils/budgetDisplay';

interface ApproveBudgetDialogProps {
    /** Total de la versión pendiente, para que el cliente confirme el monto exacto. */
    total: number;
    cantidadPartidas: number;
    isLoading?: boolean;
    /** Error del servidor al intentar aprobar. */
    error?: string | null;
    onConfirm: () => void;
    onCancel: () => void;
}

/**
 * Confirmación de aprobación del presupuesto. Además de resumir el total, exige
 * que el cliente marque que revisó las partidas y el monto antes de habilitar el
 * botón: aprobar autoriza el cobro y no se puede deshacer. Se monta solo cuando
 * está abierto (el padre lo renderiza condicionalmente), así la casilla parte
 * siempre sin marcar.
 */
export function ApproveBudgetDialog({
    total,
    cantidadPartidas,
    isLoading = false,
    error = null,
    onConfirm,
    onCancel,
}: ApproveBudgetDialogProps) {
    const [revisado, setRevisado] = useState(false);

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && !isLoading) onCancel();
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [isLoading, onCancel]);

    return (
        <div
            className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 animate-fade-in"
            onMouseDown={(e) => {
                if (e.target === e.currentTarget && !isLoading) onCancel();
            }}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-label="Aprobar presupuesto"
                className="card relative w-full max-w-[480px] p-8"
            >
                <button
                    type="button"
                    aria-label="Cerrar"
                    onClick={onCancel}
                    disabled={isLoading}
                    className="absolute right-4 top-4 text-text-muted hover:text-text-main bg-transparent border-none cursor-pointer disabled:opacity-50"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="w-16 h-16 rounded-full mx-auto mb-5 flex items-center justify-center bg-status-green/10">
                    <CheckCircle2 className="w-8 h-8 text-status-green" />
                </div>

                <h3 className="text-2xl font-bold tracking-tight text-text-main text-center">
                    Aprobar presupuesto
                </h3>
                <p className="mt-2 text-text-muted text-sm text-center">
                    Al aprobar, autoriza al taller a utilizar los repuestos indicados y avanzar con la
                    reparación. Esta acción no se puede deshacer.
                </p>

                <div className="flex justify-between items-center bg-bg-secondary rounded-xl px-5 py-4 mt-5">
                    <span className="text-text-muted">
                        Total a aprobar ({cantidadPartidas}{' '}
                        {cantidadPartidas === 1 ? 'partida' : 'partidas'}):
                    </span>
                    <span className="text-2xl font-bold">{formatMoneyCLP(total)}</span>
                </div>

                <label className="flex items-start gap-3 mt-5 text-sm text-text-main cursor-pointer">
                    <input
                        type="checkbox"
                        checked={revisado}
                        onChange={(event) => setRevisado(event.target.checked)}
                        disabled={isLoading}
                        className="mt-0.5 accent-status-green"
                    />
                    <span>
                        He revisado las partidas y el total de {formatMoneyCLP(total)}.
                    </span>
                </label>

                {error && (
                    <Alert tone="error" className="mt-4">
                        {error}
                    </Alert>
                )}

                <div className="flex flex-col sm:flex-row sm:items-center justify-end gap-3 mt-8">
                    <Button
                        type="button"
                        variant="secondary"
                        disabled={isLoading}
                        onClick={onCancel}
                        className="sm:flex-1 py-3"
                    >
                        Cancelar
                    </Button>
                    <Button
                        type="button"
                        variant="success"
                        isLoading={isLoading}
                        disabled={!revisado}
                        onClick={onConfirm}
                        className="sm:flex-1 py-3"
                    >
                        Confirmar aprobación
                    </Button>
                </div>
            </div>
        </div>
    );
}
