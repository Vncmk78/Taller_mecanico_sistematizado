import type { OrdenRepuestos, PaginaRepuestos, Repuesto } from '@/domain/entities/Repuesto';

export interface RepuestoFiltros {
    proveedorId?: number | null;
    q?: string | null;
    bajoUmbral?: boolean;
    conStock?: boolean | null;
    ordenar?: OrdenRepuestos;
    desde?: number;
    limite?: number;
}

export interface RepuestoPort {
    getRepuestos(filtros?: RepuestoFiltros): Promise<PaginaRepuestos>;
    getRepuestoById(id: number): Promise<Repuesto>;
}
