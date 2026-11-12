import type {
    CambioUmbral,
    PaginaAlertas,
    PaginaMovimientos,
    ResultadoDisponibilidad,
    ResultadoConfirmarDisponibilidad,
    ResultadoOperacionOrden,
    ResultadoMovimiento,
    ResultadoReserva,
    StockDetalle,
    TipoMovimiento,
    UmbralGeneral,
} from '@/domain/entities/Inventario';

export interface MovimientoFiltros {
    repuestoId?: number | null;
    ordenId?: number | null;
    tipo?: TipoMovimiento | null;
    proveedorId?: number | null;
    desde?: number;
    limite?: number;
}

export interface RegistrarMovimientoInput {
    claveOperacion: string;
    repuestoId: number;
    tipo: TipoMovimiento;
    cantidad: number;
    ordenId?: number | null;
    proveedorId?: number | null;
}

export interface CambiarUmbralInput {
    umbralGeneral: number;
    observacion?: string | null;
}

export interface InventarioPort {
    registrarMovimiento(input: RegistrarMovimientoInput): Promise<ResultadoMovimiento>;
    listMovimientos(filtros?: MovimientoFiltros): Promise<PaginaMovimientos>;
    getStock(repuestoId: number): Promise<StockDetalle>;
    listAlertas(): Promise<PaginaAlertas>;
    getUmbralGeneral(): Promise<UmbralGeneral>;
    cambiarUmbralGeneral(input: CambiarUmbralInput): Promise<UmbralGeneral>;
    getHistorialUmbral(repuestoId?: number | null, soloGeneral?: boolean, limite?: number): Promise<CambioUmbral[]>;
    getDisponibilidadOrden(ordenId: number): Promise<ResultadoDisponibilidad>;
    confirmarDisponibilidad(ordenId: number): Promise<ResultadoConfirmarDisponibilidad>;
    reservar(ordenId: number): Promise<ResultadoReserva>;
    consumir(ordenId: number, items: Array<{ repuestoId: number; cantidad: number }>, claveOperacion: string): Promise<ResultadoOperacionOrden>;
    liberar(ordenId: number, claveOperacion: string): Promise<ResultadoOperacionOrden>;
}
