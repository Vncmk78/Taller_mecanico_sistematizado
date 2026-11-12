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

export interface CrearRepuestoInput {
    proveedorId: number;
    nombre: string;
    stockInicial?: number;
    umbralParticular?: number | null;
}

export interface ActualizarRepuestoInput {
    nombre?: string;
    proveedorId?: number;
    umbralParticular?: number | null;
    observacion?: string | null;
}

export interface RepuestoPort {
    getRepuestos(filtros?: RepuestoFiltros): Promise<PaginaRepuestos>;
    getRepuestoById(id: number): Promise<Repuesto>;
    createRepuesto(input: CrearRepuestoInput): Promise<Repuesto>;
    updateRepuesto(id: number, input: ActualizarRepuestoInput): Promise<Repuesto>;
    deleteRepuesto(id: number): Promise<void>;
}
