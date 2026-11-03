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

    async createProveedor(input: { nombre: string; contacto: string; tipoDistribuidor?: TipoDistribuidor }): Promise<Proveedor> {
        const body: Record<string, unknown> = {
            nombre: input.nombre,
            contacto: input.contacto,
        };
        if (input.tipoDistribuidor) body.tipo_distribuidor = input.tipoDistribuidor;
        const { data } = await apiClient.post<ProveedorApi>('/proveedores', body);
        return mapProveedor(data);
    }

    async updateProveedor(id: number, input: { nombre?: string; contacto?: string; tipoDistribuidor?: TipoDistribuidor }): Promise<Proveedor> {
        const body: Record<string, unknown> = {};
        if (input.nombre !== undefined) body.nombre = input.nombre;
        if (input.contacto !== undefined) body.contacto = input.contacto;
        if (input.tipoDistribuidor !== undefined) body.tipo_distribuidor = input.tipoDistribuidor;
        const { data } = await apiClient.patch<ProveedorApi>(`/proveedores/${id}`, body);
        return mapProveedor(data);
    }

    async deleteProveedor(id: number): Promise<void> {
        await apiClient.delete(`/proveedores/${id}`);
    }
}

export const proveedorService = new ProveedorService();
