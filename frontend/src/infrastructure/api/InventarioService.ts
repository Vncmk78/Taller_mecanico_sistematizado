import type { InventarioPort } from '@/domain/ports/InventarioPort';
import type {
    MovimientoFiltros,
    RegistrarMovimientoInput,
} from '@/domain/ports/InventarioPort';
import type {
    AlertaStock as AlertaStockEntity,
    CambioUmbral as CambioUmbralEntity,
    Movimiento as MovimientoEntity,
    PaginaAlertas as PaginaAlertasEntity,
    PaginaMovimientos as PaginaMovimientosEntity,
    ResultadoMovimiento as ResultadoMovimientoEntity,
    StockDetalle as StockDetalleEntity,
    TipoMovimiento,
    UmbralGeneral as UmbralGeneralEntity,
} from '@/domain/entities/Inventario';
import apiClient from '../config/apiClient';

interface MovimientoApi {
    movimiento_id: number;
    clave_operacion: string;
    repuesto_id: number;
    tipo: TipoMovimiento;
    cantidad: number;
    orden_id: number | null;
    proveedor_id: number | null;
    fecha_hora: string;
    registrado_por_id: number;
}

interface PaginaMovimientosApi {
    total: number;
    desde: number;
    limite: number;
    movimientos: MovimientoApi[];
}

interface CompromisoApi {
    orden_id: number;
    comprometido: number;
}

interface StockApi {
    repuesto_id: number;
    nombre: string;
    proveedor_nombre: string;
    stock: number;
    comprometido: number;
    disponible: number;
    umbral_efectivo: number | null;
    bajo_umbral: boolean;
    compromisos: CompromisoApi[];
}

interface AlertaApi {
    repuesto_id: number;
    nombre: string;
    proveedor_nombre: string;
    stock: number;
    umbral_efectivo: number;
    faltan: number;
}

interface PaginaAlertasApi {
    umbral_general: number | null;
    total: number;
    alertas: AlertaApi[];
}

interface UmbralGeneralApi {
    umbral_general: number | null;
    vigente_desde: string | null;
    actualizado_por_id: number | null;
}

interface CambioUmbralApi {
    historial_id: number;
    repuesto_id: number | null;
    valor_anterior: number | null;
    valor_nuevo: number | null;
    administrador_id: number;
    fecha_hora: string;
    observacion: string | null;
}

interface ResultadoMovimientoApi {
    movimiento: MovimientoApi;
    stock: StockApi;
    alerta: { activa: boolean; nueva: boolean };
    repetido: boolean;
}

function mapMovimiento(m: MovimientoApi): MovimientoEntity {
    return {
        movimientoId: m.movimiento_id,
        claveOperacion: m.clave_operacion,
        repuestoId: m.repuesto_id,
        tipo: m.tipo,
        cantidad: m.cantidad,
        ordenId: m.orden_id,
        proveedorId: m.proveedor_id,
        fechaHora: m.fecha_hora,
        registradoPorId: m.registrado_por_id,
    };
}

function mapStock(s: StockApi): StockDetalleEntity {
    return {
        repuestoId: s.repuesto_id,
        nombre: s.nombre,
        proveedorNombre: s.proveedor_nombre,
        stock: s.stock,
        comprometido: s.comprometido,
        disponible: s.disponible,
        umbralEfectivo: s.umbral_efectivo,
        bajoUmbral: s.bajo_umbral,
        compromisos: s.compromisos.map((c) => ({ ordenId: c.orden_id, comprometido: c.comprometido })),
    };
}

function mapAlerta(a: AlertaApi): AlertaStockEntity {
    return {
        repuestoId: a.repuesto_id,
        nombre: a.nombre,
        proveedorNombre: a.proveedor_nombre,
        stock: a.stock,
        umbralEfectivo: a.umbral_efectivo,
        faltan: a.faltan,
    };
}

function mapUmbral(u: UmbralGeneralApi): UmbralGeneralEntity {
    return {
        umbralGeneral: u.umbral_general,
        vigenteDesde: u.vigente_desde,
        actualizadoPorId: u.actualizado_por_id,
    };
}

function mapCambio(c: CambioUmbralApi): CambioUmbralEntity {
    return {
        historialId: c.historial_id,
        repuestoId: c.repuesto_id,
        valorAnterior: c.valor_anterior,
        valorNuevo: c.valor_nuevo,
        administradorId: c.administrador_id,
        fechaHora: c.fecha_hora,
        observacion: c.observacion,
    };
}

class InventarioService implements InventarioPort {
    async registrarMovimiento(input: RegistrarMovimientoInput): Promise<ResultadoMovimientoEntity> {
        const body: Record<string, unknown> = {
            clave_operacion: input.claveOperacion,
            repuesto_id: input.repuestoId,
            tipo: input.tipo,
            cantidad: input.cantidad,
        };
        if (input.ordenId != null) body.orden_id = input.ordenId;
        if (input.proveedorId != null) body.proveedor_id = input.proveedorId;

        const { data } = await apiClient.post<ResultadoMovimientoApi>('/inventario/movimientos', body);
        return {
            movimiento: mapMovimiento(data.movimiento),
            stock: mapStock(data.stock),
            alerta: data.alerta,
            repetido: data.repetido,
        };
    }

    async listMovimientos(filtros: MovimientoFiltros = {}): Promise<PaginaMovimientosEntity> {
        const params: Record<string, string | number> = {};
        if (filtros.repuestoId != null) params.repuesto_id = filtros.repuestoId;
        if (filtros.ordenId != null) params.orden_id = filtros.ordenId;
        if (filtros.tipo) params.tipo = filtros.tipo;
        if (filtros.proveedorId != null) params.proveedor_id = filtros.proveedorId;
        if (typeof filtros.desde === 'number') params.desde = filtros.desde;
        if (typeof filtros.limite === 'number') params.limite = filtros.limite;

        const { data } = await apiClient.get<PaginaMovimientosApi>('/inventario/movimientos', { params });
        return {
            total: data.total,
            desde: data.desde,
            limite: data.limite,
            movimientos: data.movimientos.map(mapMovimiento),
        };
    }

    async getStock(repuestoId: number): Promise<StockDetalleEntity> {
        const { data } = await apiClient.get<StockApi>(`/inventario/stock/${repuestoId}`);
        return mapStock(data);
    }

    async listAlertas(): Promise<PaginaAlertasEntity> {
        const { data } = await apiClient.get<PaginaAlertasApi>('/inventario/alertas');
        return {
            umbralGeneral: data.umbral_general,
            total: data.total,
            alertas: data.alertas.map(mapAlerta),
        };
    }

    async getUmbralGeneral(): Promise<UmbralGeneralEntity> {
        const { data } = await apiClient.get<UmbralGeneralApi>('/inventario/umbral-general');
        return mapUmbral(data);
    }

    async cambiarUmbralGeneral(input: { umbralGeneral: number; observacion?: string | null }): Promise<UmbralGeneralEntity> {
        const body: Record<string, unknown> = { umbral_general: input.umbralGeneral };
        if (input.observacion) body.observacion = input.observacion;
        const { data } = await apiClient.put<UmbralGeneralApi>('/inventario/umbral-general', body);
        return mapUmbral(data);
    }

    async getHistorialUmbral(
        repuestoId?: number | null,
        soloGeneral = false,
        limite = 50
    ): Promise<CambioUmbralEntity[]> {
        const params: Record<string, string | number | boolean> = { limite };
        if (repuestoId != null) params.repuesto_id = repuestoId;
        if (soloGeneral) params.solo_general = true;
        const { data } = await apiClient.get<CambioUmbralApi[]>('/inventario/historial-umbral', { params });
        return data.map(mapCambio);
    }
}

export const inventarioService = new InventarioService();
