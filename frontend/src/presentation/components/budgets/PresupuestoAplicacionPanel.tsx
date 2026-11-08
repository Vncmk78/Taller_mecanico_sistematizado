import { useState } from 'react';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { Button } from '@/presentation/components/ui/Button';

export function PresupuestoAplicacionPanel({ tipo, id, ordenId, onConfirmed }: {
    tipo: 'envio' | 'decision'; id: string; ordenId: string; onConfirmed: () => void;
}) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [confirmed, setConfirmed] = useState(false);
    const comprobar = async () => {
        if (busy) return;
        setBusy(true);
        setError(null);
        try {
            if (tipo === 'envio') await presupuestoService.aplicarEnvio(id);
            else await presupuestoService.aplicarDecision(id);
            // La escritura fue confirmada; un fallo de lectura posterior no la deshace.
            setConfirmed(true);
            onConfirmed();
            try { useOrderStore.getState().updateOrder(await orderService.getOrderById(ordenId)); }
            catch { setError('La aplicación está confirmada. No se pudo actualizar el detalle de la orden; recárguelo.'); }
        } catch (err) { setError(getApiErrorMessage(err, 'La operación sigue guardada; todavía no se pudo confirmar su aplicación.')); }
        finally { setBusy(false); }
    };
    return <section className="card p-4 my-4" aria-label="Aplicación del presupuesto">
        <p>{confirmed ? 'Aplicación confirmada en la orden.' : 'El envío o la decisión está registrado. Confirme su aplicación en la orden sin repetir la operación.'}</p>
        {error && <p role="alert" className="text-status-red">{error}</p>}
        {!confirmed && <Button onClick={comprobar} isLoading={busy}>Confirmar estado de la orden</Button>}
    </section>;
}
