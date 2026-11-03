import { beforeEach, describe, expect, it, vi } from 'vitest';
import { proveedorService } from '@/infrastructure/api/ProveedorService';
import apiClient from '@/infrastructure/config/apiClient';

vi.mock('@/infrastructure/config/apiClient', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

const proveedorApi = {
    proveedor_id: 3,
    nombre: 'Repuestos del Sur',
    contacto: 'ventas@delsur.cl',
    tipo_distribuidor: 'oficial' as const,
    cantidad_repuestos: 12,
};

const paginaApi = {
    total: 1,
    desde: 0,
    limite: 200,
    proveedores: [proveedorApi],
};

describe('ProveedorService: contrato HTTP de MS3 (proveedores)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('getProveedores consulta GET /proveedores y traduce al dominio', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: paginaApi });

        const pagina = await proveedorService.getProveedores({ limite: 200 });

        expect(apiClient.get).toHaveBeenCalledWith('/proveedores', {
            params: { limite: 200 },
        });
        expect(pagina.total).toBe(1);
        expect(pagina.proveedores[0]).toEqual({
            proveedorId: 3,
            nombre: 'Repuestos del Sur',
            contacto: 'ventas@delsur.cl',
            tipoDistribuidor: 'oficial',
            cantidadRepuestos: 12,
        });
    });

    it('envía los filtros opcionales con el nombre del query string y recorta q', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: paginaApi });

        await proveedorService.getProveedores({
            q: '  sur  ',
            conRepuestos: true,
            tipoDistribuidor: 'generico',
            desde: 50,
            limite: 200,
        });

        expect(apiClient.get).toHaveBeenCalledWith('/proveedores', {
            params: {
                q: 'sur',
                con_repuestos: true,
                tipo_distribuidor: 'generico',
                desde: 50,
                limite: 200,
            },
        });
    });

    it('omite q vacío y los filtros no informados', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: paginaApi });

        await proveedorService.getProveedores({
            q: '   ',
            conRepuestos: null,
            tipoDistribuidor: null,
        });

        expect(apiClient.get).toHaveBeenCalledWith('/proveedores', { params: {} });
    });

    it('traduce el payload literal publicado por la Gateway', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: {
                total: 1,
                desde: 0,
                limite: 50,
                proveedores: [
                    {
                        proveedor_id: 3,
                        nombre: 'Repuestos del Sur',
                        contacto: 'ventas@repuestosdelsur.cl',
                        tipo_distribuidor: 'oficial',
                        cantidad_repuestos: 1,
                    },
                ],
            },
        });

        const pagina = await proveedorService.getProveedores();

        expect(pagina.proveedores[0]).toEqual({
            proveedorId: 3,
            nombre: 'Repuestos del Sur',
            contacto: 'ventas@repuestosdelsur.cl',
            tipoDistribuidor: 'oficial',
            cantidadRepuestos: 1,
        });
    });
});
