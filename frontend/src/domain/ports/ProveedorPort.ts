import type { PaginaProveedores, Proveedor, TipoDistribuidor } from '@/domain/entities/Proveedor';

export interface ProveedorFiltros {
    /** Texto libre sobre nombre o contacto (el backend ignora mayúsculas y tildes). */
    q?: string | null;
    /** true: solo con repuestos; false: solo sin repuestos. */
    conRepuestos?: boolean | null;
    tipoDistribuidor?: TipoDistribuidor | null;
    desde?: number;
    limite?: number;
}

export interface CrearProveedorInput {
    nombre: string;
    contacto: string;
    tipoDistribuidor?: TipoDistribuidor;
}

export interface ActualizarProveedorInput {
    nombre?: string;
    contacto?: string;
    tipoDistribuidor?: TipoDistribuidor;
}

export interface ProveedorPort {
    getProveedores(filtros?: ProveedorFiltros): Promise<PaginaProveedores>;
    createProveedor(input: CrearProveedorInput): Promise<Proveedor>;
    updateProveedor(id: number, input: ActualizarProveedorInput): Promise<Proveedor>;
    deleteProveedor(id: number): Promise<void>;
}
