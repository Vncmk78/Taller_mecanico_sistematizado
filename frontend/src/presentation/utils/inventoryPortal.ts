/**
 * Portal desde el que se consulta el inventario.
 *
 * `admin` conserva todas las acciones de gestión; `mechanic` muestra la misma
 * información en modo solo lectura y limita los movimientos a los que el
 * backend permite al mecánico sobre sus órdenes asignadas.
 */
export type InventoryPortalMode = 'admin' | 'mechanic';

export function isAdminInventoryMode(mode: InventoryPortalMode = 'admin'): boolean {
    return mode === 'admin';
}
