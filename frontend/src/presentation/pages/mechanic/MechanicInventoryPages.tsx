import { AdminDistributorsPage } from '@/presentation/pages/admin/AdminDistributorsPage';
import { AdminInventoryAlertsPage } from '@/presentation/pages/admin/AdminInventoryAlertsPage';
import { AdminInventoryMovementsPage } from '@/presentation/pages/admin/AdminInventoryMovementsPage';
import { AdminInventoryPage } from '@/presentation/pages/admin/AdminInventoryPage';
import { AdminStockDetailPage } from '@/presentation/pages/admin/AdminStockDetailPage';
import { AdminThresholdPage } from '@/presentation/pages/admin/AdminThresholdPage';

/**
 * El portal mecánico reutiliza las pantallas de inventario en modo `mechanic`:
 * consulta completa de stock y movimientos, sin las acciones de administración.
 */
export function MechanicInventoryPage() {
    return <AdminInventoryPage mode="mechanic" />;
}

export function MechanicInventoryAlertsPage() {
    return <AdminInventoryAlertsPage />;
}

export function MechanicInventoryMovementsPage() {
    return <AdminInventoryMovementsPage mode="mechanic" />;
}

export function MechanicStockDetailPage() {
    return <AdminStockDetailPage />;
}

export function MechanicThresholdPage() {
    return <AdminThresholdPage mode="mechanic" />;
}

export function MechanicDistributorsPage() {
    return <AdminDistributorsPage mode="mechanic" />;
}
