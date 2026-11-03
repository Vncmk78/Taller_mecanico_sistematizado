import type { PaginaProveedores, TipoDistribuidor } from '@/domain/entities/Proveedor';

export interface ProveedorFiltros {
    /** Texto libre sobre nombre o contacto (el backend ignora mayúsculas y tildes). */
    q?: string | null;
    /** true: solo con repuestos; false: solo sin repuestos. */
    conRepuestos?: boolean | null;
    tipoDistribuidor?: TipoDistribuidor | null;
    desde?: number;
    limite?: number;
}

export interface ProveedorPort {
    getProveedores(filtros?: ProveedorFiltros): Promise<PaginaProveedores>;
}
