export type TipoDistribuidor = 'oficial' | 'generico';

/** Proveedor (distribuidor) de repuestos tal como lo expone MS3. */
export interface Proveedor {
    proveedorId: number;
    nombre: string;
    contacto: string;
    tipoDistribuidor: TipoDistribuidor;
    cantidadRepuestos: number;
}

export interface PaginaProveedores {
    total: number;
    desde: number;
    limite: number;
    proveedores: Proveedor[];
}
