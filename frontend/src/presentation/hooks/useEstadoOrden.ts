import { useCallback, useEffect, useState } from 'react';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';

/**
 * Estado actual de la orden leído desde MS2 (no desde la caché), para decidir
 * si una operación de presupuesto ya guardada quedó pendiente de aplicar.
 * `null` mientras no se conoce o si la lectura falla: en ese caso la vista no
 * supone nada.
 */
export function useEstadoOrden(ordenId: string | undefined, options?: { soloPropietario?: boolean }) {
    const [estado, setEstado] = useState<number | null>(null);
    const soloPropietario = options?.soloPropietario ?? false;

    const recargar = useCallback(async () => {
        if (!ordenId) return null;
        try {
            const orden = await orderService.getOrderById(ordenId, soloPropietario ? { soloPropietario } : undefined);
            useOrderStore.getState().updateOrder(orden);
            setEstado(orden.estadoCodigo);
            return orden.estadoCodigo;
        } catch {
            setEstado(null);
            return null;
        }
    }, [ordenId, soloPropietario]);

    useEffect(() => {
        // eslint-disable-next-line react/set-state-in-effect
        void recargar();
    }, [recargar]);

    return { estado, recargar };
}
