import { beforeEach, describe, expect, it, vi } from 'vitest';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import apiClient from '@/infrastructure/config/apiClient';

// Fija el contrato HTTP de MS3 consumido por el frontend (ver
// docs/contratos-openapi.md). El dinero y las cantidades llegan como texto; el
// servicio los normaliza a number.
vi.mock('@/infrastructure/config/apiClient', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

const itemApi = {
    item_id: 11,
    tipo: 'repuesto' as const,
    descripcion: 'Kit Pastillas Freno Delanteras',
    cantidad: '1.00',
    precio_unitario: '35000.00',
    subtotal: '35000.00',
    repuesto_id: 9,
    repuesto_nombre: 'Kit Pastillas Freno Delanteras',
    proveedor_nombre: 'Distribuidor Oficial Derco',
};

const versionApi = {
    numero: 1,
    estado: 'enviada' as const,
    es_modificacion: false,
    creado_por_id: 7,
    creado_en: '2026-09-02T09:20:00-03:00',
    enviado_en: '2026-09-02T09:20:00-03:00',
    bloqueada_en: null,
    total: '108000.00',
    items: [itemApi],
    decision: null,
};

const resumenApi = {
    presupuesto_id: 501,
    orden_id: 101,
    creado_en: '2026-09-02T09:20:00-03:00',
    cantidad_versiones: 1,
    ultima_version: 1,
    estado_ultima_version: 'enviada' as const,
    total_ultima_version: '108000.00',
    version_vigente: null,
};

describe('PresupuestoService: contrato HTTP de MS3 (presupuestos)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('getByOrder consulta GET /presupuestos?orden_id y traduce el resumen', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: { total: 1, desde: 0, limite: 50, presupuestos: [resumenApi] },
        });

        const presupuesto = await presupuestoService.getByOrder('101');

        expect(apiClient.get).toHaveBeenCalledWith('/presupuestos', { params: { orden_id: '101' } });
        expect(presupuesto).toEqual({
            id: '501',
            orderId: '101',
            creadoEn: '2026-09-02T09:20:00-03:00',
            cantidadVersiones: 1,
            ultimaVersion: 1,
            estadoUltimaVersion: 'enviada',
            totalUltimaVersion: 108000,
            versionVigente: null,
            versiones: [],
        });
    });

    it('getByOrder devuelve null cuando la orden no tiene presupuesto enviado', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: { total: 0, desde: 0, limite: 50, presupuestos: [] },
        });

        expect(await presupuestoService.getByOrder('999')).toBeNull();
    });

    it('getById consulta el detalle y normaliza dinero e ítems a number', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: { ...resumenApi, versiones: [versionApi] },
        });

        const presupuesto = await presupuestoService.getById('501');

        expect(apiClient.get).toHaveBeenCalledWith('/presupuestos/501');
        expect(presupuesto.versiones[0].total).toBe(108000);
        expect(presupuesto.versiones[0].items[0]).toEqual({
            id: '11',
            tipo: 'repuesto',
            descripcion: 'Kit Pastillas Freno Delanteras',
            cantidad: 1,
            precioUnitario: 35000,
            subtotal: 35000,
            repuestoId: '9',
            repuestoNombre: 'Kit Pastillas Freno Delanteras',
            proveedorNombre: 'Distribuidor Oficial Derco',
        });
    });

    it('decidir publica POST a la decisión de la versión y mapea el resultado', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: {
                presupuesto: {
                    ...resumenApi,
                    estado_ultima_version: 'aprobada',
                    version_vigente: 1,
                    versiones: [
                        {
                            ...versionApi,
                            estado: 'aprobada',
                            decision: {
                                decision_id: 77,
                                decision: 'aprobado',
                                cliente_usuario_id: 5,
                                fecha_hora: '2026-09-03T10:00:00-03:00',
                                motivo: null,
                            },
                        },
                    ],
                },
                efecto_en_orden: 'en_reparacion',
                repuestos_faltantes: [],
                decision_id: 77,
                aplicacion_en_orden: { decision_id: 77, orden_id: 101, estado_aplicado: 5 },
            },
        });

        const resultado = await presupuestoService.decidir('501', 1, 'aprobado');

        expect(apiClient.post).toHaveBeenCalledWith('/presupuestos/501/versiones/1/decision', {
            decision: 'aprobado',
        });
        expect(resultado.efectoEnOrden).toBe('en_reparacion');
        expect(resultado.decisionId).toBe('77');
        expect(resultado.aplicacionConfirmada).toBe(true);
        expect(resultado.presupuesto.estadoUltimaVersion).toBe('aprobada');
        expect(resultado.presupuesto.versiones[0].decision?.decision).toBe('aprobado');
    });

    it('decidir un rechazo envía motivo y confirmar_cancelacion', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: {
                presupuesto: {
                    ...resumenApi,
                    estado_ultima_version: 'rechazada',
                    versiones: [{ ...versionApi, estado: 'rechazada' }],
                },
                efecto_en_orden: 'cancelado',
                repuestos_faltantes: [],
                decision_id: 88,
                aplicacion_en_orden: { decision_id: 88, orden_id: 101, estado_aplicado: 8 },
            },
        });

        await presupuestoService.decidir('501', 1, 'rechazado', '  Costo elevado  ', true);

        expect(apiClient.post).toHaveBeenCalledWith('/presupuestos/501/versiones/1/decision', {
            decision: 'rechazado',
            motivo: 'Costo elevado',
            confirmar_cancelacion: true,
        });
    });

    it('decidir un rechazo posterior a una aprobación no confirma cancelación', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: {
                presupuesto: { ...resumenApi, versiones: [versionApi] },
                efecto_en_orden: null,
                repuestos_faltantes: [],
                decision_id: 89,
                aplicacion_en_orden: null,
            },
        });

        const resultado = await presupuestoService.decidir('501', 2, 'rechazado', 'Cambio innecesario');

        expect(apiClient.post).toHaveBeenCalledWith('/presupuestos/501/versiones/2/decision', {
            decision: 'rechazado',
            motivo: 'Cambio innecesario',
            confirmar_cancelacion: false,
        });
        expect(resultado.efectoEnOrden).toBeNull();
        expect(resultado.aplicacionConfirmada).toBe(false);
    });
});
