export type TipoMovimiento =
    | 'ingreso'
    | 'ajuste'
    | 'compromiso'
    | 'consumo'
    | 'liberacion';

export interface Movimiento {
    movimientoId: number;
    claveOperacion: string;
    repuestoId: number;
    tipo: TipoMovimiento;
    cantidad: number;
    ordenId: number | null;
    proveedorId: number | null;
    fechaHora: string;
    registradoPorId: number;
}

export interface PaginaMovimientos {
    total: number;
    desde: number;
    limite: number;
    movimientos: Movimiento[];
}

export interface CompromisoOrden {
    ordenId: number;
    comprometido: number;
}

export interface StockDetalle {
    repuestoId: number;
    nombre: string;
    proveedorNombre: string;
    stock: number;
    comprometido: number;
    disponible: number;
    umbralEfectivo: number | null;
    bajoUmbral: boolean;
    compromisos: CompromisoOrden[];
}

export interface AlertaStock {
    repuestoId: number;
    nombre: string;
    proveedorNombre: string;
    stock: number;
    umbralEfectivo: number;
    faltan: number;
}

export interface PaginaAlertas {
    umbralGeneral: number | null;
    total: number;
    alertas: AlertaStock[];
}

export interface UmbralGeneral {
    umbralGeneral: number | null;
    vigenteDesde: string | null;
    actualizadoPorId: number | null;
}

export interface CambioUmbral {
    historialId: number;
    repuestoId: number | null;
    valorAnterior: number | null;
    valorNuevo: number | null;
    administradorId: number;
    fechaHora: string;
    observacion: string | null;
}

export interface ResultadoMovimiento {
    movimiento: Movimiento;
    stock: StockDetalle;
    alerta: { activa: boolean; nueva: boolean };
    repetido: boolean;
}

export interface DisponibilidadRepuesto {
    repuestoId: number;
    nombre: string;
    proveedorNombre: string;
    requerido: number;
    stock: number;
    reservadoParaOrden: number;
    comprometidoOtrasOrdenes: number;
    disponible: number;
    alcanza: boolean;
    faltan: number;
}

export interface ResultadoDisponibilidad {
    ordenId: number | null;
    disponible: boolean;
    repuestos: DisponibilidadRepuesto[];
    presupuestoId: number | null;
    version: number | null;
}