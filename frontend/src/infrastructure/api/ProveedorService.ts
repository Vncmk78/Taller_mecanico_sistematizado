import type { PaginaProveedores, Proveedor, TipoDistribuidor } from '@/domain/entities/Proveedor';
import type { ProveedorFiltros, ProveedorPort } from '@/domain/ports/ProveedorPort';
import apiClient from '../config/apiClient';

interface ProveedorApi {
    proveedor_id: number;
    nombre: string;
    contacto: string;
    tipo_distribuidor: TipoDistribuidor;
    cantidad_repuestos: number;
}

interface PaginaProveedoresApi {
    total: number;
    desde: number;
    limite: number;
    proveedores: ProveedorApi[];
}

function mapProveedor(p: ProveedorApi): Proveedor {
    return {
        proveedorId: p.proveedor_id,
        nombre: p.nombre,
        contacto: p.contacto,
        tipoDistribuidor: p.tipo_distribuidor,
        cantidadRepuestos: p.cantidad_repuestos,
    };
}

class ProveedorService implements ProveedorPort {
    async getProveedores(filtros: ProveedorFiltros = {}): Promise<PaginaProveedores> {
        const params: Record<string, string | number | boolean> = {};
        if (filtros.q && filtros.q.trim()) params.q = filtros.q.trim();
        if (typeof filtros.conRepuestos === 'boolean') params.con_repuestos = filtros.conRepuestos;
        if (filtros.tipoDistribuidor) params.tipo_distribuidor = filtros.tipoDistribuidor;
        if (typeof filtros.desde === 'number') params.desde = filtros.desde;
        if (typeof filtros.limite === 'number') params.limite = filtros.limite;

        const { data } = await apiClient.get<PaginaProveedoresApi>('/proveedores', { params });
        return {
            total: data.total,
            desde: data.desde,
            limite: data.limite,
            proveedores: data.proveedores.map(mapProveedor),
        };
    }
}

export const proveedorService = new ProveedorService();
