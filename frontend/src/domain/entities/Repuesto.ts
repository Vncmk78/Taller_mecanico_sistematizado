export type TipoDistribuidor = 'oficial' | 'generico';

export interface Repuesto {
    repuestoId: number;
    nombre: string;
    proveedorId: number;
    proveedorNombre: string;
    proveedorTipoDistribuidor: TipoDistribuidor;
    stock: number;
    umbralParticular: number | null;
    umbralEfectivo: number | null;
    bajoUmbral: boolean;
}

export interface PaginaRepuestos {
    total: number;
    desde: number;
    limite: number;
    umbralGeneral: number | null;
    repuestos: Repuesto[];
}

export type OrdenRepuestos = 'nombre' | 'stock_asc' | 'stock_desc';
