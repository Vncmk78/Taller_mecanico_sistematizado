import type { Order } from '@/domain/entities/Order';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import type { OrderPort } from '@/domain/ports/OrderPort';
import apiClient from '../config/apiClient';

// Contrato HTTP de MS2 (OrdenRespuesta) a través de la API Gateway (/api/ordenes).
// Al igual que en vehículos, el backend usa nombres en español y el dominio del
// frontend en inglés; este servicio traduce el sentido de la respuesta.
interface OrdenRespuesta {
    orden_id: number;
    vehiculo_id: number;
    ingreso_id: number;
    estado_codigo: number;
    mecanico_actual_id: number | null;
    creado_por_id: number;
    creado_en: string;
    actualizado_en: string;
}

function mapOrdenApi(o: OrdenRespuesta): Order {
    return {
        id: String(o.orden_id),
        vehicleId: String(o.vehiculo_id),
        ingresoId: o.ingreso_id,
        estadoCodigo: o.estado_codigo,
        mecanicoActualId: o.mecanico_actual_id === null ? null : String(o.mecanico_actual_id),
        creadoPorId: String(o.creado_por_id),
        creadoEn: o.creado_en,
        actualizadoEn: o.actualizado_en,
    };
}

function mapHistorialApi(h: HistorialEstadoApi): OrderHistoryEntry {
    return {
        id: String(h.historial_id),
        ordenId: String(h.orden_id),
        estadoAnteriorCodigo: h.estado_anterior,
        estadoNuevoCodigo: h.estado_nuevo,
        actorUsuarioId: h.actor_usuario_id,
        origen: h.origen,
        fecha: h.fecha_hora,
        observacion: h.observacion ?? undefined,
    };
}

// Contrato de HistorialEstado (MS2) para el endpoint futuro /ordenes/{id}/historial.
interface HistorialEstadoApi {
    historial_id: number;
    orden_id: number;
    estado_anterior: number | null;
    estado_nuevo: number;
    actor_usuario_id: number | null;
    origen: 'usuario' | 'sistema';
    fecha_hora: string;
    observacion?: string | null;
}

class OrderService implements OrderPort {
    async getOrders(): Promise<Order[]> {
        const { data } = await apiClient.get<OrdenRespuesta[]>('/ordenes');
        return data.map(mapOrdenApi);
    }

    async getOrderById(id: string): Promise<Order> {
        const { data } = await apiClient.get<OrdenRespuesta>(`/ordenes/${id}`);
        return mapOrdenApi(data);
    }

    async getOrderHistory(ordenId: string): Promise<OrderHistoryEntry[]> {
        const { data } = await apiClient.get<HistorialEstadoApi[]>(`/ordenes/${ordenId}/historial`);
        return data.map(mapHistorialApi);
    }
}

export const orderService = new OrderService();