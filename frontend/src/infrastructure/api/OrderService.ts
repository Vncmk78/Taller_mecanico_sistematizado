import type { BitacoraEntradaCrear, BitacoraEntry, RepuestoBitacora, TipoBitacora } from '@/domain/entities/Bitacora';
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

// Contrato de BitacoraRespuesta (MS2) para /ordenes/{id}/bitacora. Los repuestos
// van anidados con texto libre y cantidad: no referencian el catálogo de MS3.
interface RepuestoBitacoraApi {
    nombre: string;
    cantidad: number;
}

interface BitacoraApi {
    bitacora_id: number;
    orden_id: number;
    autor_usuario_id: number;
    tipo: TipoBitacora;
    descripcion: string;
    creado_en: string;
    repuestos: RepuestoBitacoraApi[];
}

function mapBitacoraApi(b: BitacoraApi): BitacoraEntry {
    return {
        id: String(b.bitacora_id),
        ordenId: String(b.orden_id),
        autorUsuarioId: String(b.autor_usuario_id),
        tipo: b.tipo,
        descripcion: b.descripcion,
        creadoEn: b.creado_en,
        repuestos: b.repuestos.map(
            (r): RepuestoBitacora => ({ nombre: r.nombre, cantidad: r.cantidad })
        ),
    };
}

// Cuerpo de BitacoraCrear: solo tipo y descripcion son obligatorios; repuestos
// solo se admite para tipo "accion" (el backend responde 422 si no).
interface BitacoraCrearApi {
    tipo: TipoBitacora;
    descripcion: string;
    repuestos: RepuestoBitacoraApi[];
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

    async getOrderBitacora(ordenId: string): Promise<BitacoraEntry[]> {
        const { data } = await apiClient.get<BitacoraApi[]>(`/ordenes/${ordenId}/bitacora`);
        return data.map(mapBitacoraApi);
    }

    async registrarBitacora(ordenId: string, entrada: BitacoraEntradaCrear): Promise<BitacoraEntry> {
        const cuerpo: BitacoraCrearApi = {
            tipo: entrada.tipo,
            descripcion: entrada.descripcion.trim(),
            repuestos: (entrada.repuestos ?? []).map((r) => ({
                nombre: r.nombre.trim(),
                cantidad: r.cantidad,
            })),
        };
        const { data } = await apiClient.post<BitacoraApi>(`/ordenes/${ordenId}/bitacora`, cuerpo);
        return mapBitacoraApi(data);
    }

    async cambiarEstado(ordenId: string, estadoDestino: number, observacion?: string): Promise<Order> {
        const { data } = await apiClient.patch<OrdenRespuesta>(`/ordenes/${ordenId}/estado`, {
            estado_destino: estadoDestino,
            observacion: observacion?.trim() || undefined,
        });
        return mapOrdenApi(data);
    }

    async asignarMecanico(ordenId: string, mecanicoId: string, observacion?: string): Promise<Order> {
        const { data } = await apiClient.put<OrdenRespuesta>(`/ordenes/${ordenId}/mecanico`, {
            mecanico_id: Number(mecanicoId),
            observacion: observacion?.trim() || undefined,
        });
        return mapOrdenApi(data);
    }

    async registrarEntrega(ordenId: string, observacion?: string): Promise<Order> {
        const { data } = await apiClient.post<OrdenRespuesta>(`/ordenes/${ordenId}/entrega`, {
            observacion: observacion?.trim() || undefined,
        });
        return mapOrdenApi(data);
    }

    async cancelarComoCliente(ordenId: string, motivo: string): Promise<Order> {
        const { data } = await apiClient.post<OrdenRespuesta>(`/ordenes/${ordenId}/cancelacion`, {
            motivo: motivo.trim(),
        });
        return mapOrdenApi(data);
    }
}

export const orderService = new OrderService();