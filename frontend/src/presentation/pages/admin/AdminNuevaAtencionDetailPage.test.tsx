import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import type { User, UserRole } from '@/domain/entities/User';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { AdminNuevaAtencionDetailPage } from './AdminNuevaAtencionDetailPage';

// Simulaciones de prueba del contrato acordado (Entrega C): el backend C se
// implementa en paralelo.
vi.mock('@/infrastructure/api/NuevaAtencionService', async (original) => {
    const real = await original<typeof import('@/infrastructure/api/NuevaAtencionService')>();
    return {
        RespuestaIncompletaError: real.RespuestaIncompletaError,
        nuevaAtencionService: {
            solicitar: vi.fn(), listar: vi.fn(), obtener: vi.fn(), revisar: vi.fn(), generarOrden: vi.fn(),
        },
    };
});

const pendiente: SolicitudNuevaAtencion = {
    id: '4',
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
};

const revisada = (overrides: Partial<SolicitudNuevaAtencion> = {}): SolicitudNuevaAtencion => ({
    ...pendiente,
    situacion: 'aceptada',
    respuesta: 'Lo esperamos el lunes',
    revisorId: '3',
    revisadaEn: '2026-11-08T15:00:00-03:00',
    ...overrides,
});

const orden = (overrides: Partial<Order> = {}): Order => ({
    id: '30',
    vehicleId: '9',
    ingresoId: 12,
    estadoCodigo: 1,
    mecanicoActualId: null,
    creadoPorId: '3',
    creadoEn: '2026-11-08T15:10:00-03:00',
    actualizadoEn: '2026-11-08T15:10:00-03:00',
    devueltoEn: null,
    devueltoPorId: null,
    ...overrides,
});

function iniciar(roles: UserRole[], id = '3') {
    const user: User = { id, email: 'a@taller.cl', full_name: 'Admin', role: roles[0], roles, is_active: true };
    useAuthStore.setState({ user, token: 't', isAuthenticated: true });
}

const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
const errorHttp = (status: number, data: unknown) =>
    new AxiosError(String(status), String(status), config, undefined, {
        status, statusText: String(status), data, headers: {}, config,
    });
const sinRespuesta = () => new AxiosError('timeout', 'ECONNABORTED', config);

const renderPage = () =>
    render(
        <MemoryRouter initialEntries={['/admin/nuevas-atenciones/4']}>
            <Routes>
                <Route path="/admin/nuevas-atenciones/:id" element={<AdminNuevaAtencionDetailPage />} />
            </Routes>
        </MemoryRouter>
    );

async function revisar(decision: 'Aceptar' | 'Rechazar', respuesta: string) {
    fireEvent.click(await screen.findByLabelText(decision));
    fireEvent.change(screen.getByLabelText('Respuesta para el cliente'), { target: { value: respuesta } });
    fireEvent.click(screen.getByRole('button', { name: 'Registrar revisión' }));
    const dialogo = await screen.findByRole('dialog');
    fireEvent.click(within(dialogo).getByRole('button', { name: decision === 'Aceptar' ? 'Aceptar solicitud' : 'Rechazar solicitud' }));
}

async function generar() {
    fireEvent.click(await screen.findByRole('button', { name: 'Generar orden' }));
    const dialogo = await screen.findByRole('dialog');
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Generar orden' }));
}

beforeEach(() => {
    vi.clearAllMocks();
    iniciar(['administrador']);
    useVehicleStore.setState({ vehicles: [] });
    useOrderStore.setState({ orders: [] });
});

describe('AdminNuevaAtencionDetailPage: consulta', () => {
    it('muestra el detalle con el cliente y enlaza la orden cancelada en el portal administrativo', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(pendiente);

        renderPage();

        expect(await screen.findByRole('heading', { name: 'Solicitud de nueva atención n° 4' })).toBeInTheDocument();
        expect(screen.getByText('Cliente (usuario)')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Orden n° 25' })).toHaveAttribute('href', '/admin/ordenes/25');
        expect(screen.getByRole('button', { name: 'Registrar revisión' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Generar orden' })).not.toBeInTheDocument();
    });

    it('una solicitud propia de un Administrador multirrol también enlaza a /admin', async () => {
        iniciar(['cliente', 'administrador'], '10');
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(revisada({ ordenGeneradaId: '30' }));

        renderPage();

        expect(await screen.findByRole('link', { name: 'Ver orden n° 30' })).toHaveAttribute('href', '/admin/ordenes/30');
        expect(screen.getByRole('link', { name: 'Orden n° 25' })).toHaveAttribute('href', '/admin/ordenes/25');
    });

    it('404 y otros errores se muestran con su mensaje', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockRejectedValueOnce(errorHttp(404, { detail: 'No existe' }));
        const { unmount } = renderPage();
        expect(await screen.findByText('Solicitud no encontrada.')).toBeInTheDocument();
        unmount();

        vi.mocked(nuevaAtencionService.obtener).mockRejectedValueOnce(errorHttp(403, { detail: 'Se requiere el rol Administrador' }));
        renderPage();
        expect(await screen.findByText('Se requiere el rol Administrador')).toBeInTheDocument();
    });
});

describe('AdminNuevaAtencionDetailPage: revisión', () => {
    it('exige decisión y respuesta no vacía antes de confirmar', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(pendiente);
        renderPage();

        fireEvent.click(await screen.findByRole('button', { name: 'Registrar revisión' }));
        expect(await screen.findByText('Elija aceptar o rechazar la solicitud.')).toBeInTheDocument();
        expect(screen.getByText('Escriba la respuesta que verá el cliente.')).toBeInTheDocument();

        fireEvent.click(screen.getByLabelText('Rechazar'));
        fireEvent.change(screen.getByLabelText('Respuesta para el cliente'), { target: { value: '   ' } });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar revisión' }));

        expect(screen.getByText('Escriba la respuesta que verá el cliente.')).toBeInTheDocument();
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
        expect(nuevaAtencionService.revisar).not.toHaveBeenCalled();
    });

    it('aceptar muestra la auditoría del servidor, retira el formulario y ofrece generar la orden', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(pendiente);
        vi.mocked(nuevaAtencionService.revisar).mockResolvedValue(revisada());
        renderPage();

        await revisar('Aceptar', '  Lo esperamos el lunes ');

        expect(await screen.findByText(/El servidor registró la solicitud n° 4 como Aceptada/)).toBeInTheDocument();
        expect(nuevaAtencionService.revisar).toHaveBeenCalledWith('4', 'aceptada', '  Lo esperamos el lunes ');
        expect(screen.getByText('Lo esperamos el lunes')).toBeInTheDocument();
        expect(screen.getByText('Revisada por (usuario)')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Registrar revisión' })).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Generar orden' })).toBeInTheDocument();
    });

    it('rechazar deja la solicitud rechazada sin ofrecer generar', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(pendiente);
        vi.mocked(nuevaAtencionService.revisar).mockResolvedValue(
            revisada({ situacion: 'rechazada', respuesta: 'No corresponde' })
        );
        renderPage();

        await revisar('Rechazar', 'No corresponde');

        expect(await screen.findByText(/como Rechazada/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Generar orden' })).not.toBeInTheDocument();
    });

    it('permite la autorrevisión de una cuenta Cliente+Administrador', async () => {
        iniciar(['cliente', 'administrador'], '10');
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(pendiente);
        vi.mocked(nuevaAtencionService.revisar).mockResolvedValue(revisada({ revisorId: '10' }));
        renderPage();

        await revisar('Aceptar', 'Autorrevisión');

        expect(await screen.findByText(/como Aceptada/)).toBeInTheDocument();
        expect(nuevaAtencionService.revisar).toHaveBeenCalledTimes(1);
    });

    it('una solicitud ya revisada muestra la auditoría y no un formulario editable', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(revisada({ situacion: 'rechazada', respuesta: 'No corresponde' }));
        renderPage();

        expect(await screen.findByText('No corresponde')).toBeInTheDocument();
        expect(screen.queryByLabelText('Respuesta para el cliente')).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Registrar revisión' })).not.toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: 'Revisar solicitud' })).not.toBeInTheDocument();
    });

    it('un reintento idéntico muestra la auditoría original que devuelve el servidor', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(pendiente);
        vi.mocked(nuevaAtencionService.revisar).mockResolvedValue(
            revisada({ revisadaEn: '2026-11-08T09:30:00-03:00', revisorId: '7' })
        );
        renderPage();

        await revisar('Aceptar', 'Lo esperamos el lunes');

        expect(await screen.findByText(/como Aceptada/)).toBeInTheDocument();
        expect(screen.getByText('7')).toBeInTheDocument();
    });

    it('409 por contenido distinto: muestra el detail y permite consultar la revisión existente', async () => {
        vi.mocked(nuevaAtencionService.obtener)
            .mockResolvedValueOnce(pendiente)
            .mockResolvedValueOnce(revisada({ situacion: 'rechazada', respuesta: 'Revisión de otro administrador', revisorId: '8' }));
        vi.mocked(nuevaAtencionService.revisar).mockRejectedValue(
            errorHttp(409, { detail: 'La solicitud ya fue revisada con otro contenido' })
        );
        renderPage();

        await revisar('Aceptar', 'Mi respuesta');

        expect(await screen.findByText('La solicitud ya fue revisada con otro contenido')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Consultar la solicitud' }));
        expect(await screen.findByText('Revisión de otro administrador')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Registrar revisión' })).not.toBeInTheDocument();
    });

    it('respuesta perdida: si ya figura revisada lo muestra sin atribuirlo a la petición', async () => {
        vi.mocked(nuevaAtencionService.obtener)
            .mockResolvedValueOnce(pendiente)
            .mockResolvedValueOnce(revisada({ revisorId: '8' }));
        vi.mocked(nuevaAtencionService.revisar).mockRejectedValue(sinRespuesta());
        renderPage();

        await revisar('Aceptar', 'Mi respuesta');

        expect(await screen.findByText(/Pudo registrarla esta petición u otro Administrador/)).toBeInTheDocument();
        expect(screen.getByText('8')).toBeInTheDocument();
        expect(nuevaAtencionService.revisar).toHaveBeenCalledTimes(1);
    });

    it('respuesta perdida: si sigue pendiente no concluye que no se guardó y bloquea hasta revisarlo', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(pendiente);
        vi.mocked(nuevaAtencionService.revisar).mockRejectedValue(errorHttp(504, { error: { codigo: 'TIEMPO_AGOTADO' } }));
        renderPage();

        await revisar('Aceptar', 'Mi respuesta');

        expect(await screen.findByText(/todavía figura pendiente. Eso no prueba/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Registrar revisión' })).toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: 'Ya lo revisé: permitir enviar otra vez' }));
        expect(screen.getByRole('button', { name: 'Registrar revisión' })).toBeEnabled();
    });

    it('comprobación fallida: informa resultado incierto y permite comprobar de nuevo', async () => {
        vi.mocked(nuevaAtencionService.obtener)
            .mockResolvedValueOnce(pendiente)
            .mockRejectedValueOnce(sinRespuesta())
            .mockResolvedValueOnce(revisada());
        vi.mocked(nuevaAtencionService.revisar).mockRejectedValue(sinRespuesta());
        renderPage();

        await revisar('Aceptar', 'Mi respuesta');

        expect(await screen.findByText(/Resultado incierto/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Comprobar de nuevo' }));
        expect(await screen.findByText(/Pudo registrarla esta petición u otro Administrador/)).toBeInTheDocument();
    });
});

describe('AdminNuevaAtencionDetailPage: generación de la orden', () => {
    it('aceptada sin orden: 201 muestra la orden nueva del servidor con su enlace administrativo', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(revisada());
        vi.mocked(nuevaAtencionService.generarOrden).mockResolvedValue({
            solicitud: revisada({ ordenGeneradaId: '30' }), orden: orden(), creada: true,
        });
        renderPage();

        await generar();

        expect(await screen.findByText(/Se generó la orden n° 30 \(estado Recibido\)/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Abrir orden n° 30' })).toHaveAttribute('href', '/admin/ordenes/30');
        expect(screen.queryByRole('button', { name: 'Generar orden' })).not.toBeInTheDocument();
        expect(useOrderStore.getState().orders.find((o) => o.id === '30')).toMatchObject({ estadoCodigo: 1 });
        expect(nuevaAtencionService.generarOrden).toHaveBeenCalledWith('4');
    });

    it('200: recupera la asociación existente sin duplicar y conserva el estado que informa el servidor', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(revisada());
        vi.mocked(nuevaAtencionService.generarOrden).mockResolvedValue({
            solicitud: revisada({ ordenGeneradaId: '30' }),
            orden: orden({ estadoCodigo: 5, mecanicoActualId: '40' }),
            creada: false,
        });
        renderPage();

        await generar();

        expect(await screen.findByText(/ya tenía la orden n° 30; no se creó otra. Estado actual: En reparación/)).toBeInTheDocument();
        expect(nuevaAtencionService.generarOrden).toHaveBeenCalledTimes(1);
    });

    it('aceptada con orden existente: muestra el enlace y no ofrece generar otra', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(revisada({ ordenGeneradaId: '30' }));
        renderPage();

        expect(await screen.findByRole('link', { name: 'Ver orden n° 30' })).toHaveAttribute('href', '/admin/ordenes/30');
        expect(screen.queryByRole('button', { name: 'Generar orden' })).not.toBeInTheDocument();
    });

    it.each([
        'El vehículo ya tiene la orden activa n° 28',
        'El taller ya alcanzó el máximo diario de ingresos físicos',
    ])('409 muestra el detail real sin forzar la creación: %s', async (detail) => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(revisada());
        vi.mocked(nuevaAtencionService.generarOrden).mockRejectedValue(errorHttp(409, { detail }));
        renderPage();

        await generar();

        expect(await screen.findByText(detail)).toBeInTheDocument();
        expect(screen.queryByText(/Se generó la orden/)).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Generar orden' })).toBeEnabled();
        expect(nuevaAtencionService.generarOrden).toHaveBeenCalledTimes(1);
    });

    it('bloquea el doble envío', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(revisada());
        vi.mocked(nuevaAtencionService.generarOrden).mockImplementation(() => new Promise(() => {}));
        renderPage();

        fireEvent.click(await screen.findByRole('button', { name: 'Generar orden' }));
        const dialogo = await screen.findByRole('dialog');
        const boton = within(dialogo).getByRole('button', { name: 'Generar orden' });
        fireEvent.click(boton);
        fireEvent.click(boton);

        await waitFor(() => expect(within(dialogo).getByRole('button', { name: /Cargando/ })).toBeDisabled());
        expect(nuevaAtencionService.generarOrden).toHaveBeenCalledTimes(1);
    });

    it('respuesta perdida: si el GET muestra el vínculo, lo presenta sin atribuirlo', async () => {
        vi.mocked(nuevaAtencionService.obtener)
            .mockResolvedValueOnce(revisada())
            .mockResolvedValueOnce(revisada({ ordenGeneradaId: '31' }));
        vi.mocked(nuevaAtencionService.generarOrden).mockRejectedValue(sinRespuesta());
        renderPage();

        await generar();

        expect(await screen.findByText(/Según el servidor, la solicitud está vinculada a la orden n°/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Abrir orden n° 31' })).toHaveAttribute('href', '/admin/ordenes/31');
        expect(screen.queryByText(/Se generó la orden/)).not.toBeInTheDocument();
    });

    it('respuesta incompleta o vínculo aún ausente: no afirma que falló y bloquea generar', async () => {
        const { RespuestaIncompletaError } = await import('@/infrastructure/api/NuevaAtencionService');
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(revisada());
        vi.mocked(nuevaAtencionService.generarOrden).mockRejectedValue(new RespuestaIncompletaError('incompleta'));
        renderPage();

        await generar();

        expect(await screen.findByText(/todavía no muestra una orden vinculada. Eso no prueba que la creación falló/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Generar orden' })).toBeDisabled();
        expect(screen.queryByText(/Se generó la orden/)).not.toBeInTheDocument();
    });

    it('comprobación fallida: resultado incierto y comprobar de nuevo', async () => {
        vi.mocked(nuevaAtencionService.obtener)
            .mockResolvedValueOnce(revisada())
            .mockRejectedValueOnce(sinRespuesta())
            .mockResolvedValueOnce(revisada({ ordenGeneradaId: '30' }));
        vi.mocked(nuevaAtencionService.generarOrden).mockRejectedValue(sinRespuesta());
        renderPage();

        await generar();

        expect(await screen.findByText(/Resultado incierto/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Generar orden' })).toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: 'Comprobar de nuevo' }));
        expect(await screen.findByRole('link', { name: 'Abrir orden n° 30' })).toBeInTheDocument();
        expect(nuevaAtencionService.generarOrden).toHaveBeenCalledTimes(1);
    });
});
