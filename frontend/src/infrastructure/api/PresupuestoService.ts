import type {
    DecisionCliente,
    DecisionPresupuesto,
    EstadoVersionPresupuesto,
    ItemPresupuesto,
    Presupuesto,
    ResultadoDecision,
    TipoItemPresupuesto,
    VersionPresupuesto,
} from '@/domain/entities/Presupuesto';
import type { PresupuestoPort } from '@/domain/ports/PresupuestoPort';
import apiClient from '../config/apiClient';

// Contrato HTTP de MS3 (presupuestos) a través de la API Gateway. El backend usa
// nombres en español; el dominio del frontend en inglés. El dinero y las
// cantidades viajan como texto ("38990.00") para no perder precisión.

type EstadoVersionApi = 'borrador' | 'enviada' | 'aprobada' | 'rechazada';

interface ItemSalidaApi {
    item_id: number;
    tipo: 'repuesto' | 'mano_de_obra';
    descripcion: string;
    cantidad: string | number;
    precio_unitario: string | number;
    subtotal: string | number;
    repuesto_id: number | null;
    repuesto_nombre?: string | null;
    proveedor_nombre?: string | null;
}

interface DecisionSalidaApi {
    decision_id: number;
    decision: 'aprobado' | 'rechazado';
    cliente_usuario_id: number;
    fecha_hora: string;
    motivo: string | null;
}

interface VersionDetalleApi {
    numero: number;
    estado: EstadoVersionApi;
    es_modificacion: boolean;
    creado_por_id: number;
    creado_en: string;
    enviado_en: string | null;
    bloqueada_en: string | null;
    total: string | number;
    items: ItemSalidaApi[];
    decision: DecisionSalidaApi | null;
}

interface PresupuestoResumenApi {
    presupuesto_id: number;
    orden_id: number;
    creado_en: string;
    cantidad_versiones: number;
    ultima_version: number;
    estado_ultima_version: EstadoVersionApi;
    total_ultima_version: string | number;
    version_vigente: number | null;
}

interface PresupuestoDetalleApi extends PresupuestoResumenApi {
    versiones: VersionDetalleApi[];
}

interface PaginaPresupuestosApi {
    total: number;
    desde: number;
    limite: number;
    presupuestos: PresupuestoResumenApi[];
}

interface ResultadoOperacionApi {
    presupuesto: PresupuestoDetalleApi;
    efecto_en_orden: string | null;
    decision_id: number | null;
    aplicacion_en_orden: Record<string, unknown> | null;
}

function toNumber(value: string | number): number {
    const parsed = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function mapItemApi(item: ItemSalidaApi): ItemPresupuesto {
    return {
        id: String(item.item_id),
        tipo: item.tipo as TipoItemPresupuesto,
        descripcion: item.descripcion,
        cantidad: toNumber(item.cantidad),
        precioUnitario: toNumber(item.precio_unitario),
        subtotal: toNumber(item.subtotal),
        repuestoId: item.repuesto_id === null ? null : String(item.repuesto_id),
        repuestoNombre: item.repuesto_nombre ?? undefined,
        proveedorNombre: item.proveedor_nombre ?? undefined,
    };
}

function mapDecisionApi(decision: DecisionSalidaApi): DecisionPresupuesto {
    return {
        id: String(decision.decision_id),
        decision: decision.decision as DecisionCliente,
        fecha: decision.fecha_hora,
        motivo: decision.motivo ?? undefined,
    };
}

function mapVersionApi(version: VersionDetalleApi): VersionPresupuesto {
    return {
        numero: version.numero,
        estado: version.estado as EstadoVersionPresupuesto,
        esModificacion: version.es_modificacion,
        creadoEn: version.creado_en,
        enviadoEn: version.enviado_en ?? undefined,
        bloqueadaEn: version.bloqueada_en ?? undefined,
        total: toNumber(version.total),
        items: version.items.map(mapItemApi),
        decision: version.decision ? mapDecisionApi(version.decision) : undefined,
    };
}

function mapResumenApi(resumen: PresupuestoResumenApi): Presupuesto {
    return {
        id: String(resumen.presupuesto_id),
        orderId: String(resumen.orden_id),
        creadoEn: resumen.creado_en,
        cantidadVersiones: resumen.cantidad_versiones,
        ultimaVersion: resumen.ultima_version,
        estadoUltimaVersion: resumen.estado_ultima_version as EstadoVersionPresupuesto,
        totalUltimaVersion: toNumber(resumen.total_ultima_version),
        versionVigente: resumen.version_vigente,
        versiones: [],
    };
}

function mapDetalleApi(detalle: PresupuestoDetalleApi): Presupuesto {
    return {
        ...mapResumenApi(detalle),
        versiones: detalle.versiones.map(mapVersionApi),
    };
}

class PresupuestoService implements PresupuestoPort {
    async getByOrder(ordenId: string): Promise<Presupuesto | null> {
        const { data } = await apiClient.get<PaginaPresupuestosApi>('/presupuestos', {
            params: { orden_id: ordenId },
        });
        const resumen = data.presupuestos[0];
        return resumen ? mapResumenApi(resumen) : null;
    }

    async getById(presupuestoId: string): Promise<Presupuesto> {
        const { data } = await apiClient.get<PresupuestoDetalleApi>(`/presupuestos/${presupuestoId}`);
        return mapDetalleApi(data);
    }

    async decidir(
        presupuestoId: string,
        numero: number,
        decision: DecisionCliente,
        motivo?: string,
        confirmarCancelacion?: boolean
    ): Promise<ResultadoDecision> {
        const body: Record<string, unknown> = { decision };
        if (decision === 'rechazado') {
            body.motivo = motivo?.trim() || undefined;
            body.confirmar_cancelacion = Boolean(confirmarCancelacion);
        }
        const { data } = await apiClient.post<ResultadoOperacionApi>(
            `/presupuestos/${presupuestoId}/versiones/${numero}/decision`,
            body
        );
        return {
            presupuesto: mapDetalleApi(data.presupuesto),
            efectoEnOrden: (data.efecto_en_orden as ResultadoDecision['efectoEnOrden']) ?? null,
            decisionId: data.decision_id === null ? null : String(data.decision_id),
            aplicacionConfirmada: data.aplicacion_en_orden !== null,
        };
    }
}

export const presupuestoService = new PresupuestoService();
