import { useEffect, useMemo, useState } from 'react';
import type { Order } from '@/domain/entities/Order';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import { orderService } from '@/infrastructure/api/OrderService';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { useBudgetStore } from '@/infrastructure/stores/useBudgetStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';

export interface ClientBudgetItem {
    order: Order;
    presupuesto: Presupuesto;
}

// Solo las órdenes que ya alcanzaron la etapa de presupuesto (o posterior) pueden
// tener uno visible para el cliente; antes de eso no se consulta MS3.
const ESTADO_MINIMO_PRESUPUESTO = 3;

// Los presupuestos pendientes de decisión van primero; el resto por fecha de
// actualización de la orden (más reciente primero).
function sortBudgets(a: ClientBudgetItem, b: ClientBudgetItem): number {
    const pendienteA = a.presupuesto.estadoUltimaVersion === 'enviada' ? 0 : 1;
    const pendienteB = b.presupuesto.estadoUltimaVersion === 'enviada' ? 0 : 1;
    if (pendienteA !== pendienteB) return pendienteA - pendienteB;
    return a.order.actualizadoEn < b.order.actualizadoEn ? 1 : -1;
}

/**
 * Listado "Mis Presupuestos": MS3 no expone un listado global para el cliente, así
 * que se parte de sus órdenes y se consulta el presupuesto de cada una. Combina el
 * estado de la carga de órdenes con el del store de presupuestos para no confundir
 * "sin presupuestos" con "no se pudieron cargar".
 */
export function useClientBudgets() {
    const orders = useOrderStore((s) => s.orders);
    const fetchOrders = useOrderStore((s) => s.fetchOrders);
    const ordersStatus = useOrderStore((s) => s.status);
    const ordersError = useOrderStore((s) => s.error);
    const ordersOffline = useOrderStore((s) => s.isOffline);

    const presupuestos = useBudgetStore((s) => s.presupuestos);
    const fetchForOrders = useBudgetStore((s) => s.fetchForOrders);
    const budgetStatus = useBudgetStore((s) => s.status);
    const budgetError = useBudgetStore((s) => s.error);
    const budgetOffline = useBudgetStore((s) => s.isOffline);
    const requestId = useBudgetStore((s) => s.requestId);

    const [reloadKey, setReloadKey] = useState(0);
    const [completedKey, setCompletedKey] = useState<number | null>(null);

    useEffect(() => {
        let active = true;
        (async () => {
            await fetchOrders(() => orderService.getOrders());
            if (!active) return;
            const candidatas = useOrderStore
                .getState()
                .orders.filter((order) => order.estadoCodigo >= ESTADO_MINIMO_PRESUPUESTO);
            await fetchForOrders(
                candidatas.map((order) => order.id),
                (ordenId) => presupuestoService.getByOrder(ordenId)
            );
            if (active) setCompletedKey(reloadKey);
        })();
        return () => {
            active = false;
        };
    }, [reloadKey, fetchOrders, fetchForOrders]);

    const items = useMemo(() => {
        const byOrderId = new Map(presupuestos.map((presupuesto) => [presupuesto.orderId, presupuesto]));
        return orders
            .filter((order) => byOrderId.has(order.id))
            .map((order) => ({ order, presupuesto: byOrderId.get(order.id)! }))
            .sort(sortBudgets);
    }, [orders, presupuestos]);

    const loading = completedKey !== reloadKey || budgetStatus === 'loading';
    const isOffline = ordersOffline || budgetOffline;
    const error = budgetError ?? ordersError;
    const failed = (ordersStatus === 'error' || budgetStatus === 'error') && items.length === 0;

    return {
        items,
        loading,
        error,
        isOffline,
        requestId,
        failed,
        refetch: () => setReloadKey((key) => key + 1),
    };
}
