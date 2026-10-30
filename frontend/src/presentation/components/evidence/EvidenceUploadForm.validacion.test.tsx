import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { TAMANO_MAXIMO_EVIDENCIA_BYTES, type Evidencia } from '@/domain/entities/Evidencia';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { EvidenceUploadForm } from './EvidenceUploadForm';

/**
 * Pruebas del formulario de carga de evidencia: validaciones antes de enviar,
 * datos que se mandan según el contexto, estado de los controles durante la
 * subida, limpieza tras el éxito y recuperación después de un error.
 * (Los casos base de progreso, éxito y error están en EvidenceUploadForm.test.tsx.)
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

const evidencia: Evidencia = {
    id: 'ev-9',
    orderId: '31',
    presupuestoId: null,
    contexto: 'reparacion',
    tipoArchivo: 'foto',
    visibleCliente: true,
    estado: 'confirmada',
    nombreOriginal: 'disco.jpg',
    contentType: 'image/jpeg',
    tamanoBytes: 2048,
    creadaEn: '2026-10-20T11:00:00-03:00',
};

function foto(nombre = 'disco.jpg', tipo = 'image/jpeg'): File {
    return new File(['contenido'], nombre, { type: tipo });
}

function conTamano(file: File, bytes: number): File {
    Object.defineProperty(file, 'size', { value: bytes });
    return file;
}

function renderForm(onSuccess?: (e: Evidencia) => void) {
    return render(
        <ToastProvider>
            <EvidenceUploadForm orderId="31" onSuccess={onSuccess} />
        </ToastProvider>
    );
}

const inputArchivo = () => screen.getByLabelText(/Archivo/) as HTMLInputElement;
const botonSubir = () => screen.getByRole('button', { name: /Subir evidencia/ });
const formulario = () => screen.getByRole('form', { name: 'Subir evidencia' });

function seleccionar(file: File) {
    fireEvent.change(inputArchivo(), { target: { files: [file] } });
}

describe('EvidenceUploadForm: validaciones antes de enviar', () => {
    beforeEach(() => {
        useEvidenceStore.getState().reset();
        vi.clearAllMocks();
    });

    it('sin archivo el botón está deshabilitado y enviar el formulario pide uno', async () => {
        renderForm();

        expect(botonSubir()).toBeDisabled();
        fireEvent.submit(formulario());

        expect(await screen.findByText('Selecciona una foto o un video.')).toBeInTheDocument();
        expect(inputArchivo()).toHaveAttribute('aria-invalid', 'true');
        expect(inputArchivo().getAttribute('aria-describedby')).toBe(
            'evidencia-archivo-hint evidencia-archivo-error'
        );
        expect(document.getElementById('evidencia-archivo-error')).toHaveTextContent(
            'Selecciona una foto o un video.'
        );
        expect(evidenciaService.crear).not.toHaveBeenCalled();
    });

    it('describe el campo de archivo con el formato y el tamaño permitidos', () => {
        renderForm();

        expect(inputArchivo().getAttribute('aria-describedby')).toBe('evidencia-archivo-hint');
        expect(document.getElementById('evidencia-archivo-hint')).toHaveTextContent(
            'Formatos permitidos: imágenes y videos. Tamaño máximo 12 MB.'
        );
    });

    it('al elegir un archivo muestra su nombre y tamaño y habilita el envío', () => {
        renderForm();
        seleccionar(conTamano(foto('frenos.jpg'), 2048));

        expect(screen.getByText('frenos.jpg · 2 KB')).toBeInTheDocument();
        expect(botonSubir()).toBeEnabled();
    });

    it('acepta videos además de fotos', async () => {
        vi.mocked(evidenciaService.crear).mockResolvedValue({ ...evidencia, tipoArchivo: 'video' });
        renderForm();
        seleccionar(foto('prueba-ruta.mp4', 'video/mp4'));
        fireEvent.click(botonSubir());

        await waitFor(() => expect(evidenciaService.crear).toHaveBeenCalledTimes(1));
        expect(vi.mocked(evidenciaService.crear).mock.calls[0][0].archivo.name).toBe('prueba-ruta.mp4');
    });

    it.each([
        ['un PDF', 'informe.pdf', 'application/pdf'],
        ['un archivo sin tipo', 'sin-extension', ''],
    ])('rechaza %s', async (_caso, nombre, tipo) => {
        renderForm();
        seleccionar(foto(nombre, tipo));
        fireEvent.click(botonSubir());

        expect(await screen.findByText('Solo se permiten imágenes o videos.')).toBeInTheDocument();
        expect(evidenciaService.crear).not.toHaveBeenCalled();
    });

    it('acepta un archivo justo en el límite de 12 MB y rechaza uno de un byte más', async () => {
        vi.mocked(evidenciaService.crear).mockResolvedValue(evidencia);
        renderForm();

        seleccionar(conTamano(foto('justo.jpg'), TAMANO_MAXIMO_EVIDENCIA_BYTES + 1));
        fireEvent.click(botonSubir());
        expect(await screen.findByText('El archivo supera el límite de 12 MB.')).toBeInTheDocument();
        expect(evidenciaService.crear).not.toHaveBeenCalled();

        seleccionar(conTamano(foto('justo.jpg'), TAMANO_MAXIMO_EVIDENCIA_BYTES));
        fireEvent.click(botonSubir());
        await waitFor(() => expect(evidenciaService.crear).toHaveBeenCalledTimes(1));
    });

    it('elegir otro archivo borra el error anterior', async () => {
        renderForm();
        seleccionar(foto('notas.txt', 'text/plain'));
        fireEvent.click(botonSubir());
        expect(await screen.findByText('Solo se permiten imágenes o videos.')).toBeInTheDocument();

        seleccionar(foto());
        expect(screen.queryByText('Solo se permiten imágenes o videos.')).not.toBeInTheDocument();
    });
});

describe('EvidenceUploadForm: datos enviados según el contexto', () => {
    beforeEach(() => {
        useEvidenceStore.getState().reset();
        vi.clearAllMocks();
    });

    it('envía el contexto elegido y la marca de visible para el cliente', async () => {
        vi.mocked(evidenciaService.crear).mockResolvedValue(evidencia);
        renderForm();

        fireEvent.change(screen.getByLabelText('Contexto'), { target: { value: 'reparacion' } });
        fireEvent.click(screen.getByLabelText('Visible para el cliente'));
        seleccionar(foto());
        fireEvent.click(botonSubir());

        await waitFor(() =>
            expect(evidenciaService.crear).toHaveBeenCalledWith(
                expect.objectContaining({
                    ordenId: '31',
                    contexto: 'reparacion',
                    visibleCliente: true,
                    presupuestoId: null,
                }),
                expect.any(Function)
            )
        );
    });

    it('ofrece los cuatro contextos oficiales en español', () => {
        renderForm();
        const opciones = Array.from(
            (screen.getByLabelText('Contexto') as HTMLSelectElement).options
        ).map((o) => [o.value, o.textContent]);

        expect(opciones).toEqual([
            ['diagnostico', 'Diagnóstico'],
            ['presupuesto', 'Presupuesto'],
            ['reparacion', 'Reparación'],
            ['resultado_final', 'Resultado final'],
        ]);
    });

    it('en contexto presupuesto oculta la casilla: esa evidencia siempre la ve el cliente', async () => {
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue({ id: '77' } as unknown as Presupuesto);
        renderForm();
        expect(screen.getByLabelText('Visible para el cliente')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Contexto'), { target: { value: 'presupuesto' } });

        expect(screen.queryByLabelText('Visible para el cliente')).not.toBeInTheDocument();
        expect(screen.getByText(/siempre es visible para el cliente/)).toBeInTheDocument();
        await waitFor(() => expect(presupuestoService.getByOrder).toHaveBeenCalledWith('31'));
    });

    it('consulta el presupuesto de la orden una sola vez aunque se cambie de contexto', async () => {
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue({ id: '77' } as unknown as Presupuesto);
        renderForm();
        const contexto = screen.getByLabelText('Contexto');

        fireEvent.change(contexto, { target: { value: 'presupuesto' } });
        await waitFor(() => expect(presupuestoService.getByOrder).toHaveBeenCalledTimes(1));
        fireEvent.change(contexto, { target: { value: 'diagnostico' } });
        fireEvent.change(contexto, { target: { value: 'presupuesto' } });

        await act(async () => {});
        expect(presupuestoService.getByOrder).toHaveBeenCalledTimes(1);
    });

    it.each([
        ['la orden no tiene presupuesto', () => vi.mocked(presupuestoService.getByOrder).mockResolvedValue(null)],
        ['falla la consulta del presupuesto', () =>
            vi.mocked(presupuestoService.getByOrder).mockRejectedValue(new Error('caído'))],
    ])('no sube evidencia de presupuesto si %s', async (_caso, preparar) => {
        preparar();
        renderForm();

        fireEvent.change(screen.getByLabelText('Contexto'), { target: { value: 'presupuesto' } });
        expect(await screen.findByText('Esta orden no tiene un presupuesto registrado.')).toBeInTheDocument();

        seleccionar(foto());
        fireEvent.click(botonSubir());

        expect(
            await screen.findByText('Esta orden no tiene un presupuesto al que asociar la evidencia.')
        ).toBeInTheDocument();
        expect(evidenciaService.crear).not.toHaveBeenCalled();
    });

    it('mientras llega el presupuesto pide esperar en vez de subir sin asociarlo', async () => {
        vi.mocked(presupuestoService.getByOrder).mockReturnValue(new Promise(() => {}));
        renderForm();

        fireEvent.change(screen.getByLabelText('Contexto'), { target: { value: 'presupuesto' } });
        seleccionar(foto());
        fireEvent.click(botonSubir());

        expect(await screen.findByText('Esperando el presupuesto de la orden...')).toBeInTheDocument();
        expect(evidenciaService.crear).not.toHaveBeenCalled();
    });

    it('un error del presupuesto no marca el archivo como inválido', async () => {
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(null);
        renderForm();

        fireEvent.change(screen.getByLabelText('Contexto'), { target: { value: 'presupuesto' } });
        expect(await screen.findByText('Esta orden no tiene un presupuesto registrado.')).toBeInTheDocument();
        seleccionar(foto());
        fireEvent.click(botonSubir());

        expect(
            await screen.findByText('Esta orden no tiene un presupuesto al que asociar la evidencia.')
        ).toBeInTheDocument();
        expect(inputArchivo()).not.toHaveAttribute('aria-invalid');
        expect(inputArchivo().getAttribute('aria-describedby')).toBe('evidencia-archivo-hint');
    });
});

describe('EvidenceUploadForm: durante y después de la subida', () => {
    beforeEach(() => {
        useEvidenceStore.getState().reset();
        vi.clearAllMocks();
    });

    it('bloquea los controles y evita un segundo envío mientras sube', async () => {
        let terminar: (e: Evidencia) => void = () => {};
        vi.mocked(evidenciaService.crear).mockImplementation(
            () => new Promise<Evidencia>((resolve) => { terminar = resolve; })
        );
        renderForm();
        seleccionar(foto());
        fireEvent.click(botonSubir());

        expect(await screen.findByText('Subiendo evidencia...')).toBeInTheDocument();
        // El botón pasa a "Cargando..." y queda deshabilitado.
        expect(screen.getByRole('button', { name: /Cargando/ })).toBeDisabled();
        expect(screen.getByLabelText('Contexto')).toBeDisabled();
        expect(screen.getByLabelText('Visible para el cliente')).toBeDisabled();

        fireEvent.submit(formulario());
        fireEvent.submit(formulario());
        expect(evidenciaService.crear).toHaveBeenCalledTimes(1);

        await act(async () => terminar(evidencia));
        expect(screen.queryByText('Subiendo evidencia...')).not.toBeInTheDocument();
    });

    it('tras el éxito limpia el archivo, avisa y entrega la evidencia creada', async () => {
        vi.mocked(evidenciaService.crear).mockResolvedValue(evidencia);
        const onSuccess = vi.fn();
        renderForm(onSuccess);

        seleccionar(foto());
        fireEvent.click(botonSubir());

        await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(evidencia));
        // Aviso en el formulario y en el toast.
        await waitFor(() => expect(screen.getAllByText('Evidencia subida correctamente.')).toHaveLength(2));
        expect(inputArchivo().value).toBe('');
        expect(screen.queryByText(/disco\.jpg ·/)).not.toBeInTheDocument();
        expect(botonSubir()).toBeDisabled();
    });

    it('elegir un archivo nuevo después del éxito quita el aviso anterior', async () => {
        vi.mocked(evidenciaService.crear).mockResolvedValue(evidencia);
        renderForm();
        seleccionar(foto());
        fireEvent.click(botonSubir());
        await waitFor(() => expect(useEvidenceStore.getState().uploadStatus).toBe('success'));

        seleccionar(foto('otra.jpg'));

        expect(useEvidenceStore.getState().uploadStatus).toBe('idle');
        expect(screen.getByRole('button', { name: /Subir evidencia/ })).toBeEnabled();
    });

    it('muestra el detalle y la referencia del error para soporte', async () => {
        vi.mocked(evidenciaService.crear).mockRejectedValue({
            isAxiosError: true,
            response: {
                status: 422,
                data: { detail: 'El archivo está dañado.', error: { request_id: 'req-123' } },
                headers: {},
            },
        });
        renderForm();
        seleccionar(foto());
        fireEvent.click(botonSubir());

        expect(await screen.findByText('El archivo está dañado.', { exact: false })).toBeInTheDocument();
        expect(screen.getByText('Referencia: req-123')).toBeInTheDocument();
    });

    it('después de un error se puede reintentar con el mismo archivo', async () => {
        vi.mocked(evidenciaService.crear)
            .mockRejectedValueOnce({ isAxiosError: true })
            .mockResolvedValueOnce(evidencia);
        const onSuccess = vi.fn();
        renderForm(onSuccess);

        seleccionar(foto());
        fireEvent.click(botonSubir());
        expect(await screen.findByText(/Sin conexión/)).toBeInTheDocument();
        expect(botonSubir()).toBeEnabled();

        fireEvent.click(botonSubir());

        await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(evidencia));
        expect(screen.queryByText(/Sin conexión/)).not.toBeInTheDocument();
        expect(evidenciaService.crear).toHaveBeenCalledTimes(2);
    });
});
