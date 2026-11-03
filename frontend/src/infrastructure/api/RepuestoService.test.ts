import { beforeEach, describe, expect, it, vi } from 'vitest';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import apiClient from '@/infrastructure/config/apiClient';

vi.mock('@/infrastructure/config/apiClient', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

const repuestoApi = {
    repuesto_id: 7,
    nombre: 'Filtro de aceite',
    proveedor_id: 3,
    proveedor_nombre: 'Repuestos del Sur',
    proveedor_tipo_distribuidor: 'oficial' as const,
    stock: 10,
    umbral_particular: 8,
    umbral_efectivo: 5,
    bajo_umbral: false,
};

const paginaApi = {
    total: 1,
    desde: 0,
    limite: 200,
    umbral_general: 5,
    repuestos: [repuestoApi],
};

describe('RepuestoService: contrato HTTP de MS3 (repuestos)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('getRepuestos consulta GET /repuestos y traduce al dominio', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: paginaApi });

        const pagina = await repuestoService.getRepuestos({ limite: 200 });

        expect(apiClient.get).toHaveBeenCalledWith('/repuestos', {
            params: { limite: 200 },
        });
        expect(pagina).toEqual({
            total: 1,
            desde: 0,
            limite: 200,
            umbralGeneral: 5,
            repuestos: [
                {
                    repuestoId: 7,
                    nombre: 'Filtro de aceite',
                    proveedorId: 3,
                    proveedorNombre: 'Repuestos del Sur',
                    proveedorTipoDistribuidor: 'oficial',
                    stock: 10,
                    umbralParticular: 8,
                    umbralEfectivo: 5,
                    bajoUmbral: false,
                },
            ],
        });
    });

    it('envía los filtros opcionales con el nombre del query string y recorta q', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: paginaApi });

        await repuestoService.getRepuestos({
            proveedorId: 3,
            q: '  filtro  ',
            bajoUmbral: true,
            conStock: false,
            ordenar: 'stock_asc',
            desde: 10,
            limite: 50,
        });

        expect(apiClient.get).toHaveBeenCalledWith('/repuestos', {
            params: {
                proveedor_id: 3,
                q: 'filtro',
                bajo_umbral: true,
                con_stock: false,
                ordenar: 'stock_asc',
                desde: 10,
                limite: 50,
            },
        });
    });

    it('omite proveedor nulo, q vacío y los filtros no informados', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: paginaApi });

        await repuestoService.getRepuestos({
            proveedorId: null,
            q: '   ',
            bajoUmbral: undefined,
            conStock: null,
            ordenar: undefined,
        });

        expect(apiClient.get).toHaveBeenCalledWith('/repuestos', { params: {} });
    });

    it('getRepuestoById consulta GET /repuestos/{id} y traduce al dominio', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: repuestoApi });

        const repuesto = await repuestoService.getRepuestoById(7);

        expect(apiClient.get).toHaveBeenCalledWith('/repuestos/7');
        expect(repuesto).toEqual({
            repuestoId: 7,
            nombre: 'Filtro de aceite',
            proveedorId: 3,
            proveedorNombre: 'Repuestos del Sur',
            proveedorTipoDistribuidor: 'oficial',
            stock: 10,
            umbralParticular: 8,
            umbralEfectivo: 5,
            bajoUmbral: false,
        });
    });

    it('conserva umbralEfectivo nulo cuando el backend no envía umbral general', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: {
                ...paginaApi,
                umbral_general: null,
                repuestos: [{ ...repuestoApi, umbral_efectivo: null }],
            },
        });

        const pagina = await repuestoService.getRepuestos({ limite: 200 });

        expect(pagina.umbralGeneral).toBeNull();
        expect(pagina.repuestos[0].umbralEfectivo).toBeNull();
    });
});