import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import type { User, UserRole } from '@/domain/entities/User';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { NuevaAtencionSection } from './NuevaAtencionSection';

// Simulaciones de prueba del contrato acordado (Entrega B): el backend B se
// implementa en paralelo.
vi.mock('@/infrastructure/api/NuevaAtencionService', () => ({
    nuevaAtencionService: { solicitar: vi.fn(), listar: vi.fn(), obtener: vi.fn() },
}));

const cancelada: Order = {
    id: '25',
    vehicleId: '9',
    ingresoId: 12,
    estadoCodigo: 8,
    mecanicoActualId: null,
    creadoPorId: '3',
    creadoEn: '2026-11-08T09:00:00-03:00',
    actualizadoEn: '2026-11-08T10:00:00-03:00',
    devueltoEn: null,
    devueltoPorId: null,
};

function solicitud(overrides: Partial<SolicitudNuevaAtencion> = {}): SolicitudNuevaAtencion {
    return {
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
        ...overrides,
    };
}

const pagina = (items: SolicitudNuevaAtencion[]) => ({ items, total: items.length, limit: 20, offset: 0 });

function iniciar(roles: UserRole[], id = '10') {
    const user: User = { id, email: 'c@taller.cl', full_name: 'Cliente', role: roles[0], roles, is_active: true };
    useAuthStore.setState({ user, token: 't', isAuthenticated: true });
}

const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
const errorHttp = (status: number, data: unknown) =>
    new AxiosError(String(status), String(status), config, undefined, {
        status, statusText: String(status), data, headers: {}, config,
    });
const sinRespuesta = () => new AxiosError('timeout', 'ECONNABORTED', config);

function renderSeccion(order: Order = cancelada) {
    return render(
        <MemoryRouter>
            <NuevaAtencionSection order={order} />
        </MemoryRouter>
    );
}

async function escribirYEnviar(texto: string) {
    const campo = await screen.findByLabelText('¿Qué necesita que revise el taller?');
    fireEvent.change(campo, { target: { value: texto } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar solicitud' }));
}

beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
    vi.mocked(nuevaAtencionService.listar).mockResolvedValue(pagina([]));
});

describe('NuevaAtencionSection: visibilidad y roles', () => {
    it('el Cliente ve el formulario en su orden Cancelada, aunque el vehículo no esté devuelto', async () => {
        iniciar(['cliente']);
        renderSeccion();

        expect(await screen.findByLabelText('¿Qué necesita que revise el taller?')).toBeInTheDocument();
        expect(screen.getByText(/no es necesario haber retirado el vehículo/)).toBeInTheDocument();
        expect(nuevaAtencionService.listar).toHaveBeenCalledWith({ ordenCanceladaId: '25' }, { limit: 20, offset: 0 });
    });

    it('una cuenta multirrol con Cliente también puede solicitar (MS2 verifica la propiedad)', async () => {
        iniciar(['administrador', 'cliente']);
        renderSeccion();

        expect(await screen.findByRole('button', { name: 'Enviar solicitud' })).toBeInTheDocument();
    });

    it.each([[['mecanico']], [['administrador']], [['mecanico', 'administrador']]] as UserRole[][][])(
        'sin rol Cliente (%j) no se muestra',
        (roles) => {
            iniciar(roles);
            renderSeccion();

            expect(screen.queryByRole('heading', { name: 'Nueva atención' })).not.toBeInTheDocument();
            expect(nuevaAtencionService.listar).not.toHaveBeenCalled();
        }
    );

    it.each([1, 6, 7])('no aparece en una orden en estado %i', (estadoCodigo) => {
        iniciar(['cliente']);
        renderSeccion({ ...cancelada, estadoCodigo });

        expect(screen.queryByRole('heading', { name: 'Nueva atención' })).not.toBeInTheDocument();
    });
});

describe('NuevaAtencionSection: validación y envío', () => {
    it.each(['', '    \n  '])('una descripción vacía o con solo espacios no se envía (%j)', async (texto) => {
        iniciar(['cliente']);
        renderSeccion();

        await escribirYEnviar(texto);

        expect(await screen.findByText(/Describa lo que necesita/)).toBeInTheDocument();
        expect(nuevaAtencionService.solicitar).not.toHaveBeenCalled();
    });

    it('más de 2000 caracteres recortados no se envían; 2000 con espacios exteriores sí', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.solicitar).mockResolvedValue({ solicitud: solicitud(), creada: true });
        renderSeccion();

        await escribirYEnviar('a'.repeat(2001));
        expect(await screen.findByText(/no puede superar 2000 caracteres/)).toBeInTheDocument();
        expect(nuevaAtencionService.solicitar).not.toHaveBeenCalled();

        await escribirYEnviar(`  ${'a'.repeat(2000)}  `);
        await waitFor(() => expect(nuevaAtencionService.solicitar).toHaveBeenCalledTimes(1));
        expect(screen.getByText('0/2000 caracteres')).toBeInTheDocument();
    });

    it('201: informa la solicitud nueva y muestra la lista del servidor sin duplicarla', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.solicitar).mockResolvedValue({ solicitud: solicitud(), creada: true });
        vi.mocked(nuevaAtencionService.listar)
            .mockResolvedValueOnce(pagina([]))
            .mockResolvedValueOnce(pagina([solicitud()]));
        renderSeccion();

        await escribirYEnviar('  Ruido al frenar ');

        expect(await screen.findByText(/Solicitud n° 4 enviada/)).toHaveTextContent('no reserva una hora ni crea una orden');
        expect(nuevaAtencionService.solicitar).toHaveBeenCalledWith('25', '  Ruido al frenar ');
        const lista = await screen.findByRole('list', { name: 'Solicitudes de la orden 25' });
        expect(within(lista).getAllByRole('listitem')).toHaveLength(1);
        expect(screen.getByText(/está pendiente de revisión/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Enviar solicitud' })).not.toBeInTheDocument();
    });

    it('200: informa que ya existía la pendiente idéntica y no agrega otra', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.solicitar).mockResolvedValue({ solicitud: solicitud(), creada: false });
        vi.mocked(nuevaAtencionService.listar)
            .mockResolvedValueOnce(pagina([]))
            .mockResolvedValueOnce(pagina([solicitud()]));
        renderSeccion();

        await escribirYEnviar('Ruido al frenar');

        expect(await screen.findByText(/Ya existía una solicitud pendiente con la misma descripción \(n° 4\); no se creó otra/)).toBeInTheDocument();
        const lista = await screen.findByRole('list', { name: 'Solicitudes de la orden 25' });
        expect(within(lista).getAllByRole('listitem')).toHaveLength(1);
    });

    it('bloquea el doble envío mientras la petición está en curso', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.solicitar).mockImplementation(() => new Promise(() => {}));
        renderSeccion();

        await escribirYEnviar('Ruido al frenar');
        const formulario = screen.getByRole('form', { name: 'Solicitar nueva atención' });
        fireEvent.submit(formulario);
        fireEvent.submit(formulario);

        await waitFor(() => expect(screen.getByRole('button', { name: /Cargando/ })).toBeDisabled());
        expect(nuevaAtencionService.solicitar).toHaveBeenCalledTimes(1);
    });
});

describe('NuevaAtencionSection: rechazos del servidor', () => {
    it.each([
        [403, 'Se requiere el rol Cliente'],
        [404, 'Orden no encontrada'],
        [422, 'La descripción no puede estar vacía'],
    ])('%i muestra el detail real', async (status, detail) => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.solicitar).mockRejectedValue(errorHttp(status, { detail }));
        renderSeccion();

        await escribirYEnviar('Ruido al frenar');

        expect(await screen.findByText(detail)).toBeInTheDocument();
        expect(screen.queryByText(/enviada/)).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Ver solicitudes de esta orden' })).not.toBeInTheDocument();
    });

    it('409 muestra el detail y permite consultar las solicitudes existentes', async () => {
        iniciar(['cliente']);
        const detail = 'Ya existe una solicitud pendiente o aceptada para esta orden';
        vi.mocked(nuevaAtencionService.solicitar).mockRejectedValue(errorHttp(409, { detail }));
        vi.mocked(nuevaAtencionService.listar)
            .mockResolvedValueOnce(pagina([]))
            .mockResolvedValueOnce(pagina([solicitud({ id: '7', descripcion: 'Desde otra pestaña' })]));
        renderSeccion();

        await escribirYEnviar('Ruido al frenar');

        expect(await screen.findByText(detail)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Ver solicitudes de esta orden' }));
        expect(await screen.findByText('Desde otra pestaña')).toBeInTheDocument();
        expect(nuevaAtencionService.listar).toHaveBeenCalledTimes(2);
    });
});

describe('NuevaAtencionSection: solicitudes existentes', () => {
    it('una rechazada se conserva y permite solicitar nuevamente', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue(
            pagina([solicitud({ situacion: 'rechazada', respuesta: 'No corresponde' })])
        );
        renderSeccion();

        expect(await screen.findByText('Rechazada')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Enviar solicitud' })).toBeInTheDocument();
    });

    it('una aceptada con orden generada bloquea y enlaza a esa orden', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue(
            pagina([solicitud({ situacion: 'aceptada', respuesta: 'Lo recibimos el lunes', ordenGeneradaId: '30', revisorId: '3' })])
        );
        renderSeccion();

        const enlace = await screen.findByRole('link', { name: 'Ver orden generada n° 30' });
        expect(enlace).toHaveAttribute('href', '/client/ordenes/30');
        expect(screen.getByText(/Si esa orden también se cancela, la próxima solicitud se hace desde ella/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Enviar solicitud' })).not.toBeInTheDocument();
    });

    it('si no se pueden consultar las solicitudes, lo informa y deja que MS2 decida el envío', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.listar).mockRejectedValue(errorHttp(500, { detail: 'Fallo de MS2' }));
        renderSeccion();

        expect(await screen.findByText('Fallo de MS2')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Enviar solicitud' })).toBeInTheDocument();
    });
});

describe('NuevaAtencionSection: respuesta perdida', () => {
    it('muestra lo que registra el servidor sin atribuirlo a la petición y bloquea hasta revisar', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.solicitar).mockRejectedValue(sinRespuesta());
        vi.mocked(nuevaAtencionService.listar)
            .mockResolvedValueOnce(pagina([]))
            .mockResolvedValueOnce(pagina([solicitud({ situacion: 'rechazada', descripcion: 'Otra descripción' })]));
        renderSeccion();

        await escribirYEnviar('Ruido al frenar');

        expect(await screen.findByText(/pudieron originarse en esta u otra pestaña/)).toBeInTheDocument();
        expect(screen.getByText('Otra descripción')).toBeInTheDocument();
        expect(screen.queryByText(/enviada\./)).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Enviar solicitud' })).toBeDisabled();
        expect(nuevaAtencionService.solicitar).toHaveBeenCalledTimes(1);

        fireEvent.click(screen.getByRole('button', { name: 'Ya lo revisé: permitir enviar otra vez' }));
        expect(screen.getByRole('button', { name: 'Enviar solicitud' })).toBeEnabled();
    });

    it('si todavía no aparece nada, no lo presenta como prueba de que no se guardó', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.solicitar).mockRejectedValue(errorHttp(504, { error: { codigo: 'TIEMPO_AGOTADO' } }));
        renderSeccion();

        await escribirYEnviar('Ruido al frenar');

        expect(await screen.findByText(/Eso no prueba que no se haya guardado/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Enviar solicitud' })).toBeDisabled();
    });

    it('si la comprobación falla informa resultado incierto y permite comprobar de nuevo', async () => {
        iniciar(['cliente']);
        vi.mocked(nuevaAtencionService.solicitar).mockRejectedValue(sinRespuesta());
        vi.mocked(nuevaAtencionService.listar)
            .mockResolvedValueOnce(pagina([]))
            .mockRejectedValueOnce(sinRespuesta())
            .mockResolvedValueOnce(pagina([solicitud()]));
        renderSeccion();

        await escribirYEnviar('Ruido al frenar');

        expect(await screen.findByText(/Resultado incierto/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Comprobar de nuevo' }));

        expect(await screen.findByText('Ruido al frenar')).toBeInTheDocument();
        expect(screen.getByText(/pudieron originarse en esta u otra pestaña/)).toBeInTheDocument();
        expect(screen.getByText(/está pendiente de revisión/)).toBeInTheDocument();
        expect(nuevaAtencionService.solicitar).toHaveBeenCalledTimes(1);
    });
});
