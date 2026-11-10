import { beforeEach, describe, expect, it, vi } from 'vitest';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import apiClient from '@/infrastructure/config/apiClient';

vi.mock('@/infrastructure/config/apiClient', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(),
    },
}));

describe('InventarioService: contrato HTTP de inventario', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('getDisponibilidadOrden consulta GET /inventario/ordenes/{id}/disponibilidad', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: {
                orden_id: 101,
                disponible: false,
                repuestos: [
                    {
                        repuesto_id: 12,
                        nombre: 'Pastillas',
                        proveedor_nombre: 'Prov',
                        requerido: 2,
                        stock: 1,
                        reservado_para_orden: 0,
                        comprometido_otras_ordenes: 0,
                        disponible: 1,
                        alcanza: false,
                        faltan: 1,
                    },
                ],
                presupuesto_id: 501,
                version: 1,
            },
        });

        const resultado = await inventarioService.getDisponibilidadOrden(101);

        expect(apiClient.get).toHaveBeenCalledWith('/inventario/ordenes/101/disponibilidad');
        expect(resultado.disponible).toBe(false);
        expect(resultado.repuestos[0].faltan).toBe(1);
        expect(resultado.presupuestoId).toBe(501);
    });

    it('reservar publica POST /inventario/ordenes/{id}/reserva', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: {
                orden_id: 101,
                reservado: true,
                faltantes: [],
                movimientos: [],
            },
        });

        const resultado = await inventarioService.reservar(101);

        expect(apiClient.post).toHaveBeenCalledWith('/inventario/ordenes/101/reserva');
        expect(resultado.reservado).toBe(true);
    });

    it('confirmarDisponibilidad publica el contrato que reserva y continúa la orden', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: {
                clave_operacion: 'orden-101-v1',
                orden_id: 101,
                version_presupuesto: 2,
                repuestos: [{ repuesto_id: 12, cantidad: 2 }],
                aplicacion_confirmada: true,
            },
        });

        const resultado = await inventarioService.confirmarDisponibilidad(101);

        expect(apiClient.post).toHaveBeenCalledWith('/inventario/ordenes/101/disponibilidad');
        expect(resultado).toEqual({
            claveOperacion: 'orden-101-v1',
            ordenId: 101,
            versionPresupuesto: 2,
            repuestos: [{ repuestoId: 12, cantidad: 2 }],
            aplicacionConfirmada: true,
        });
    });

    it('reservar mapea faltantes cuando no alcanza stock', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: {
                orden_id: 101,
                reservado: false,
                faltantes: [
                    { repuesto_id: 12, nombre: 'Pastillas', solicitado: 2, disponible: 1, faltan: 1 },
                ],
                movimientos: [],
            },
        });

        const resultado = await inventarioService.reservar(101);

        expect(resultado.reservado).toBe(false);
        expect(resultado.faltantes[0]).toEqual({
            repuestoId: 12,
            nombre: 'Pastillas',
            solicitado: 2,
            disponible: 1,
            faltan: 1,
        });
    });

    it('consumir publica POST /inventario/ordenes/{id}/consumos con clave_operacion', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: { orden_id: 101, movimientos: [], repetido: false },
        });

        await inventarioService.consumir(101, [{ repuestoId: 12, cantidad: 1 }], 'clave-1');

        expect(apiClient.post).toHaveBeenCalledWith('/inventario/ordenes/101/consumos', {
            clave_operacion: 'clave-1',
            items: [{ repuesto_id: 12, cantidad: 1 }],
        });
    });

    it('liberar publica POST /inventario/ordenes/{id}/liberacion', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: { orden_id: 101, movimientos: [], repetido: true },
        });

        const resultado = await inventarioService.liberar(101, 'clave-2');

        expect(apiClient.post).toHaveBeenCalledWith('/inventario/ordenes/101/liberacion', {
            clave_operacion: 'clave-2',
        });
        expect(resultado.repetido).toBe(true);
    });
});
