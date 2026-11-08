import { describe, expect, it } from 'vitest';
import {
    admiteGenerarOrden,
    admiteRevision,
    bloqueaNuevaSolicitud,
    DESCRIPCION_SOLICITUD_MAX,
    validarDescripcionSolicitud,
    validarRespuestaRevision,
    type SolicitudNuevaAtencion,
} from './SolicitudNuevaAtencion';

const solicitud = (overrides: Partial<SolicitudNuevaAtencion> = {}): SolicitudNuevaAtencion => ({
    id: '1',
    ordenCanceladaId: '25',
    vehiculoId: '9',
    clienteUsuarioId: '10',
    descripcion: 'Ruido al frenar',
    solicitadaEn: '2026-11-08T14:00:00-03:00',
    situacion: 'pendiente',
    respuesta: null,
    revisorId: null,
    revisadaEn: null,
    ordenGeneradaId: null,
    ...overrides,
});

describe('validarDescripcionSolicitud', () => {
    it('rechaza el texto vacío o solo con espacios', () => {
        expect(validarDescripcionSolicitud('')).toMatch(/Describa/);
        expect(validarDescripcionSolicitud('   \n\t ')).toMatch(/Describa/);
    });

    it('acepta exactamente 2000 caracteres y cuenta sin los espacios exteriores', () => {
        expect(validarDescripcionSolicitud('a'.repeat(DESCRIPCION_SOLICITUD_MAX))).toBeNull();
        expect(validarDescripcionSolicitud(`   ${'a'.repeat(DESCRIPCION_SOLICITUD_MAX)}   `)).toBeNull();
    });

    it('rechaza más de 2000 caracteres recortados', () => {
        expect(validarDescripcionSolicitud('a'.repeat(DESCRIPCION_SOLICITUD_MAX + 1))).toMatch(/2000/);
    });
});

describe('bloqueaNuevaSolicitud', () => {
    it('pendiente y aceptada bloquean, también la aceptada que ya generó orden', () => {
        expect(bloqueaNuevaSolicitud(solicitud())).toBe(true);
        expect(bloqueaNuevaSolicitud(solicitud({ situacion: 'aceptada' }))).toBe(true);
        expect(bloqueaNuevaSolicitud(solicitud({ situacion: 'aceptada', ordenGeneradaId: '30' }))).toBe(true);
    });

    it('una rechazada permite otra solicitud', () => {
        expect(bloqueaNuevaSolicitud(solicitud({ situacion: 'rechazada', respuesta: 'No corresponde' }))).toBe(false);
    });
});

describe('revisión y generación', () => {
    it('la respuesta de la revisión es obligatoria, sin máximo inventado', () => {
        expect(validarRespuestaRevision('')).toMatch(/respuesta/);
        expect(validarRespuestaRevision('  \n ')).toMatch(/respuesta/);
        expect(validarRespuestaRevision('x'.repeat(5000))).toBeNull();
    });

    it('solo una pendiente admite revisión', () => {
        expect(admiteRevision(solicitud())).toBe(true);
        expect(admiteRevision(solicitud({ situacion: 'aceptada' }))).toBe(false);
        expect(admiteRevision(solicitud({ situacion: 'rechazada' }))).toBe(false);
    });

    it('solo una aceptada sin orden admite generar la orden', () => {
        expect(admiteGenerarOrden(solicitud({ situacion: 'aceptada' }))).toBe(true);
        expect(admiteGenerarOrden(solicitud({ situacion: 'aceptada', ordenGeneradaId: '30' }))).toBe(false);
        expect(admiteGenerarOrden(solicitud())).toBe(false);
        expect(admiteGenerarOrden(solicitud({ situacion: 'rechazada' }))).toBe(false);
    });
});

