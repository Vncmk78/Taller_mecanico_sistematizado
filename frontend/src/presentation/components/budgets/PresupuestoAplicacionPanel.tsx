import { useState } from 'react';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { Button } from '@/presentation/components/ui/Button';

const TEXTOS = {
    envio: {
        titulo: 'Envío registrado, pendiente de aplicar en la orden',
        detalle: 'El presupuesto ya quedó enviado al cliente, pero la orden todavía no pasó a "Esperando aprobación". No vuelva a enviarlo: reintente solo la aplicación.',
        referencia: 'Presupuesto',
    },
    decision: {
        titulo: 'Decisión registrada, pendiente de aplicar en la orden',
        detalle: 'Su decisión ya quedó guardada, pero la orden todavía no refleja el cambio. No vuelva a aprobar ni rechazar: reintente solo la aplicación.',
        referencia: 'Decisión',
    },
} as const;

/**
 * Operación de presupuesto ya guardada en MS3 cuyo efecto en la orden (MS2) no
 * se confirmó (respuesta 503). Usa la ruta de reintento idempotente del
 * contrato: no crea otro envío ni otra decisión. Tras un reintento exitoso, la
 * vista que lo contiene vuelve a leer presupuesto y orden desde el servidor.
 */
export function PresupuestoAplicacionPanel({ tipo, id, onConfirmed }: {
    tipo: 'envio' | 'decision';
    id: string;
    ordenId?: string;
    onConfirmed: () => void | Promise<void>;
}) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const textos = TEXTOS[tipo];

    const reintentar = async () => {
        if (busy) return;
        setBusy(true);
        setError(null);
        try {
            if (tipo === 'envio') await presupuestoService.aplicarEnvio(id);
            else await presupuestoService.aplicarDecision(id);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Todavía no se pudo aplicar. La operación sigue guardada; puede reintentar más tarde.'));
            setBusy(false);
            return;
        }
        try {
            await onConfirmed();
        } finally {
            setBusy(false);
        }
    };

    return (
        <section className="card p-4 my-4 border border-status-yellow" role="status" aria-label="Aplicación pendiente del presupuesto">
            <p className="font-semibold">{textos.titulo}</p>
            <p className="text-text-muted text-sm my-2">{textos.detalle}</p>
            <p className="text-text-muted text-xs mb-3">{textos.referencia} n° {id}</p>
            {error && <p role="alert" className="text-status-red mb-3">{error}</p>}
            <Button onClick={reintentar} isLoading={busy}>Reintentar aplicación en la orden</Button>
        </section>
    );
}
