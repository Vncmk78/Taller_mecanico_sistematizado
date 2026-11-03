import type { PaginaRepuestos, Repuesto } from '@/domain/entities/Repuesto';
import type { RepuestoFiltros, RepuestoPort } from '@/domain/ports/RepuestoPort';
import apiClient from '../config/apiClient';

interface RepuestoApi {
    repuesto_id: number;
    nombre: string;
    proveedor_id: number;
    proveedor_nombre: string;
    proveedor_tipo_distribuidor: 'oficial' | 'generico';
    stock: number;
    umbral_particular: number | null;
    umbral_efectivo: number | null;
    bajo_umbral: boolean;
}

interface PaginaRepuestosApi {
    total: number;
    desde: number;
    limite: number;
    umbral_general: number | null;
    repuestos: RepuestoApi[];
}

function mapRepuesto(r: RepuestoApi): Repuesto {
    return {
        repuestoId: r.repuesto_id,
        nombre: r.nombre,
        proveedorId: r.proveedor_id,
        proveedorNombre: r.proveedor_nombre,
        proveedorTipoDistribuidor: r.proveedor_tipo_distribuidor,
        stock: r.stock,
        umbralParticular: r.umbral_particular,
        umbralEfectivo: r.umbral_efectivo,
        bajoUmbral: r.bajo_umbral,
    };
}

class RepuestoService implements RepuestoPort {
    async getRepuestos(filtros: RepuestoFiltros = {}): Promise<PaginaRepuestos> {
        const params: Record<string, string | number | boolean> = {};
        if (filtros.proveedorId != null) params.proveedor_id = filtros.proveedorId;
        if (filtros.q && filtros.q.trim()) params.q = filtros.q.trim();
        if (typeof filtros.bajoUmbral === 'boolean') params.bajo_umbral = filtros.bajoUmbral;
        if (typeof filtros.conStock === 'boolean') params.con_stock = filtros.conStock;
        if (filtros.ordenar) params.ordenar = filtros.ordenar;
        if (typeof filtros.desde === 'number') params.desde = filtros.desde;
        if (typeof filtros.limite === 'number') params.limite = filtros.limite;

        const { data } = await apiClient.get<PaginaRepuestosApi>('/repuestos', { params });
        return {
            total: data.total,
            desde: data.desde,
            limite: data.limite,
            umbralGeneral: data.umbral_general,
            repuestos: data.repuestos.map(mapRepuesto),
        };
    }

    async getRepuestoById(id: number): Promise<Repuesto> {
        const { data } = await apiClient.get<RepuestoApi>(`/repuestos/${id}`);
        return mapRepuesto(data);
    }
}

export const repuestoService = new RepuestoService();
