import type { Order } from '@/domain/entities/Order';
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

class OrderService implements OrderPort {
    async getOrders(): Promise<Order[]> {
        const { data } = await apiClient.get<OrdenRespuesta[]>('/ordenes');
        return data.map(mapOrdenApi);
    }

    async getOrderById(id: string): Promise<Order> {
        const { data } = await apiClient.get<OrdenRespuesta>(`/ordenes/${id}`);
        return mapOrdenApi(data);
    }
}

export const orderService = new OrderService();