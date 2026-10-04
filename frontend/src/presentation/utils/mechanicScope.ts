import type { Order } from '@/domain/entities/Order';
import type { Vehicle } from '@/domain/entities/Vehicle';

/**
 * Segunda barrera de alcance del portal del mecánico, análoga al filtro por
 * `clientId` que hace el portal del cliente.
 *
 * La Gateway ya devuelve únicamente las órdenes asignadas al mecánico
 * autenticado (`_filtro_visibilidad` de MS2 compara `mecanico_actual_id` con el
 * `usuario_id` del JWT), pero la caché de `useOrderStore` es compartida entre
 * portales. Como `mecanicoActualId` y `user.id` son ambos el `usuario_id` de
 * MS1, se pueden comparar directamente.
 *
 * Sin `mechanicId` no hay identidad contra la cual verificar, así que no se
 * muestra ninguna orden en lugar de exponer la caché completa.
 */
export function filterOrdersByMechanic(orders: Order[], mechanicId: string | null | undefined): Order[] {
    if (!mechanicId) return [];
    return orders.filter((order) => order.mecanicoActualId === mechanicId);
}

/**
 * Acota los vehículos a los que aparecen en las órdenes del mecánico. Online
 * `GET /vehiculos/asignados` ya devuelve exactamente esa colección, así que el
 * filtro no descarta nada; offline sí evita que se vean los vehículos que otro
 * portal dejó en la caché compartida.
 */
export function filterVehiclesByOrders(vehicles: Vehicle[], orders: Order[]): Vehicle[] {
    const assignedIds = new Set(orders.map((order) => order.vehicleId));
    return vehicles.filter((vehicle) => assignedIds.has(vehicle.id));
}