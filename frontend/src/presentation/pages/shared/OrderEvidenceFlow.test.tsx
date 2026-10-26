import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Evidencia, EvidenciaEntradaCrear } from '@/domain/entities/Evidencia';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { OrderEvidenceSection } from '@/presentation/components/evidence/OrderEvidenceSection';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { ClientOrderEvidencePage } from '@/presentation/pages/client/ClientOrderEvidencePage';
import { OrderEvidencePage } from './OrderEvidencePage';

/**
 * Flujo completo de evidencia multimedia, de punta a punta en el frontend:
 * el mecánico sube fotos y videos de una orden y el cliente ve solo lo que el
 * taller marcó como visible. El backend (MS4 vía Gateway) se reemplaza por un
 * servidor falso en memoria que se comporta como el real: guarda lo subido,
 * informa el progreso y filtra por visibilidad cuando consulta el cliente.
 */

vi.mock('@/infrastructure/api/EvidenciaService', () => ({
    evidenciaService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        getDownloadUrl: vi.fn(),
        crear: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/PresupuestoService', () => ({
    presupuestoService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        decidir: vi.fn(),
    },
}));

type Rol = 'mecanico' | 'cliente';

const servidor = {
    rol: 'mecanico' as Rol,
    evidencias: [] as Evidencia[],
    siguienteId: 1,
    fallarProximaSubida: false,
};

function instalarServidorFalso() {
    servidor.rol = 'mecanico';
    servidor.evidencias = [];
    servidor.siguienteId = 1;
    servidor.fallarProximaSubida = false;

    vi.mocked(evidenciaService.getByOrder).mockImplementation(async (ordenId: string) =>
        servidor.evidencias.filter(
            (e) => e.orderId === ordenId && (servidor.rol !== 'cliente' || e.visibleCliente)
        )
    );
    vi.mocked(evidenciaService.crear).mockImplementation(
        async (entrada: EvidenciaEntradaCrear, onProgress?: (p: number) => void) => {
            onProgress?.(40);
            if (servidor.fallarProximaSubida) {
                servidor.fallarProximaSubida = false;
                throw { isAxiosError: true, response: { status: 500, data: {} } };
            }
            onProgress?.(100);
            const nueva: Evidencia = {
                id: `ev-${servidor.siguienteId++}`,
                orderId: entrada.ordenId,
                presupuestoId: entrada.presupuestoId ?? null,
                contexto: entrada.contexto,
                tipoArchivo: entrada.archivo.type.startsWith('video/') ? 'video' : 'foto',
                visibleCliente: entrada.visibleCliente ?? false,
                estado: 'confirmada',
                nombreOriginal: entrada.archivo.name,
                contentType: entrada.archivo.type,
                tamanoBytes: entrada.archivo.size,
                creadaEn: '2026-10-20T10:00:00-03:00',
            };
            servidor.evidencias.push(nueva);
            return nueva;
        }
    );
    vi.mocked(evidenciaService.getDownloadUrl).mockImplementation(async (id: string) => ({
        url: `https://archivos.taller.example/${id}?firma=temporal`,
        expiraEn: 300,
    }));
    vi.mocked(presupuestoService.getByOrder).mockResolvedValue({ id: '501' } as unknown as Presupuesto);
}

function renderPersonal() {
    servidor.rol = 'mecanico';
    return render(
        <ToastProvider>
            <MemoryRouter initialEntries={['/mechanic/ordenes/101/evidencias']}>
                <Routes>
                    <Route
                        path="/mechanic/ordenes/:id/evidencias"
                        element={
                            <OrderEvidencePage backTo="/mechanic/ordenes" backLabel="Volver" canUpload />
                        }
                    />
                </Routes>
            </MemoryRouter>
        </ToastProvider>
    );
}

/** El cliente entra en otra sesión: su navegador no tiene la caché del mecánico. */
function renderCliente() {
    servidor.rol = 'cliente';
    useEvidenceStore.getState().reset();
    return render(
        <MemoryRouter initialEntries={['/client/ordenes/101/evidencias']}>
            <Routes>
                <Route path="/client/ordenes/:id/evidencias" element={<ClientOrderEvidencePage />} />
            </Routes>
        </MemoryRouter>
    );
}

async function subir(
    nombre: string,
    { tipo = 'image/jpeg', contexto = 'diagnostico', visible = false } = {}
) {
    fireEvent.change(screen.getByLabelText('Contexto'), { target: { value: contexto } });
    const casilla = screen.queryByLabelText('Visible para el cliente') as HTMLInputElement | null;
    if (casilla && casilla.checked !== visible) fireEvent.click(casilla);
    fireEvent.change(screen.getByLabelText(/Archivo/), {
        target: { files: [new File(['contenido'], nombre, { type: tipo })] },
    });
    // En contexto presupuesto el botón espera a que llegue el presupuesto de la orden.
    await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));
        expect(servidor.evidencias.some((e) => e.nombreOriginal === nombre)).toBe(true);
    });
    expect(await screen.findByText(nombre)).toBeInTheDocument();
}

describe('Flujo de evidencia: el mecánico sube y el cliente la ve', () => {
    beforeEach(() => {
        useEvidenceStore.getState().reset();
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false, requestId: null });
        vi.clearAllMocks();
        instalarServidorFalso();
    });

    it('lo subido aparece en la galería del personal sin recargar la página', async () => {
        renderPersonal();
        expect(await screen.findByText('Aún no hay evidencia multimedia')).toBeInTheDocument();

        await subir('pastillas-gastadas.jpg');

        expect(screen.queryByText('Aún no hay evidencia multimedia')).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Ver pastillas-gastadas.jpg' })).toBeInTheDocument();
        // La galería se actualizó desde la respuesta de la subida, sin volver a pedir el listado.
        expect(evidenciaService.getByOrder).toHaveBeenCalledTimes(1);
        expect(servidor.evidencias).toHaveLength(1);
    });

    it('el cliente ve solo la evidencia que el taller marcó como visible', async () => {
        const personal = renderPersonal();
        await screen.findByText('Aún no hay evidencia multimedia');
        await subir('pastillas-gastadas.jpg', { visible: true });
        await subir('nota-interna.jpg', { visible: false });
        personal.unmount();

        renderCliente();

        expect(await screen.findByText('pastillas-gastadas.jpg')).toBeInTheDocument();
        expect(screen.queryByText('nota-interna.jpg')).not.toBeInTheDocument();
    });

    it('la evidencia del presupuesto queda asociada y siempre la ve el cliente', async () => {
        const personal = renderPersonal();
        await screen.findByText('Aún no hay evidencia multimedia');
        await subir('cotizacion-disco.jpg', { contexto: 'presupuesto' });
        personal.unmount();

        expect(servidor.evidencias[0]).toMatchObject({
            contexto: 'presupuesto',
            presupuestoId: '501',
            visibleCliente: true,
        });

        renderCliente();
        expect(await screen.findByText('cotizacion-disco.jpg')).toBeInTheDocument();
        expect(screen.getByText('Presupuesto')).toBeInTheDocument();
    });

    it('el cliente ve el video recién subido y lo abre en la vista previa', async () => {
        const personal = renderPersonal();
        await screen.findByText('Aún no hay evidencia multimedia');
        await subir('diagnostico-frenos.jpg', { visible: true });
        await subir('prueba-de-ruta.mp4', { tipo: 'video/mp4', contexto: 'resultado_final', visible: true });
        personal.unmount();

        renderCliente();
        expect(await screen.findByText('prueba-de-ruta.mp4')).toBeInTheDocument();
        expect(screen.getByText('diagnostico-frenos.jpg')).toBeInTheDocument();

        fireEvent.click(await screen.findByRole('button', { name: 'Reproducir prueba-de-ruta.mp4' }));
        const dialogo = screen.getByRole('dialog', { name: 'Vista previa de prueba-de-ruta.mp4' });
        expect(dialogo.querySelector('video')).toHaveAttribute(
            'src',
            'https://archivos.taller.example/ev-2?firma=temporal'
        );

        fireEvent.keyDown(document, { key: 'Escape' });
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('el personal abre la vista previa de una foto recién subida y la puede descargar', async () => {
        const abrir = vi.spyOn(window, 'open').mockImplementation(() => null);
        renderPersonal();
        await screen.findByText('Aún no hay evidencia multimedia');
        await subir('alternador.jpg');

        const ver = screen.getByRole('button', { name: 'Ver alternador.jpg' });
        await waitFor(() => expect(ver).toBeEnabled());
        fireEvent.click(ver);

        const dialogo = screen.getByRole('dialog', { name: 'Vista previa de alternador.jpg' });
        fireEvent.click(within(dialogo).getByRole('button', { name: /Descargar/ }));
        expect(abrir).toHaveBeenCalledWith(
            'https://archivos.taller.example/ev-1?firma=temporal',
            '_blank',
            'noopener,noreferrer'
        );

        fireEvent.click(within(dialogo).getByRole('button', { name: 'Cerrar' }));
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
        abrir.mockRestore();
    });

    it('si la subida falla no aparece nada nuevo y al reintentar se completa el flujo', async () => {
        renderPersonal();
        await screen.findByText('Aún no hay evidencia multimedia');

        servidor.fallarProximaSubida = true;
        fireEvent.change(screen.getByLabelText(/Archivo/), {
            target: { files: [new File(['x'], 'bateria.jpg', { type: 'image/jpeg' })] },
        });
        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));

        expect(await screen.findByText('El servidor tuvo un problema. Intente más tarde.')).toBeInTheDocument();
        expect(screen.getByText('Aún no hay evidencia multimedia')).toBeInTheDocument();
        expect(servidor.evidencias).toHaveLength(0);

        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));

        expect(await screen.findByRole('button', { name: 'Ver bateria.jpg' })).toBeInTheDocument();
        expect(screen.queryByText('El servidor tuvo un problema. Intente más tarde.')).not.toBeInTheDocument();
        expect(servidor.evidencias).toHaveLength(1);
    });

    it('sin permiso de carga se ve la galería pero no el formulario', async () => {
        servidor.evidencias.push({
            id: 'ev-previa',
            orderId: '101',
            presupuestoId: null,
            contexto: 'reparacion',
            tipoArchivo: 'foto',
            visibleCliente: false,
            estado: 'confirmada',
            nombreOriginal: 'cambio-correa.jpg',
            contentType: 'image/jpeg',
            tamanoBytes: 1000,
            creadaEn: '2026-10-19T10:00:00-03:00',
        });

        render(
            <ToastProvider>
                <MemoryRouter>
                    <OrderEvidenceSection orderId="101" />
                </MemoryRouter>
            </ToastProvider>
        );

        expect(await screen.findByText('cambio-correa.jpg')).toBeInTheDocument();
        expect(screen.queryByRole('form', { name: 'Subir evidencia' })).not.toBeInTheDocument();
    });
});
