import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { Upload } from 'lucide-react';
import {
    CONTEXTO_EVIDENCIA_LABEL,
    TAMANO_MAXIMO_EVIDENCIA_BYTES,
    esContentTypeEvidenciaPermitido,
    type ContextoEvidencia,
    type Evidencia,
} from '@/domain/entities/Evidencia';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ProgressBar } from '@/presentation/components/ui/ProgressBar';
import { useToast } from '@/presentation/components/ui/toastContext';
import { useEvidenceUpload } from '@/presentation/hooks/useEvidenceUpload';
import { formatBytes } from '@/presentation/utils/evidenceDisplay';

const CONTEXTOS: ContextoEvidencia[] = ['diagnostico', 'presupuesto', 'reparacion', 'resultado_final'];

const INPUT_CLASS =
    'w-full py-2.5 px-3 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue file:mr-3 file:rounded-md file:border-0 file:bg-primary-blue file:px-3 file:py-1.5 file:text-white file:cursor-pointer';

interface EvidenceUploadFormProps {
    orderId: string;
    onSuccess?: (evidencia: Evidencia) => void;
    className?: string;
}

type EstadoPresupuesto = 'idle' | 'loading' | 'listo' | 'ausente';

/**
 * Formulario de carga de evidencia (Mecánico/Administrador). Muestra el progreso
 * real de la subida, confirma el éxito y explica los errores (validación local,
 * del servidor y falta de conexión). En contexto `presupuesto` obtiene el
 * presupuesto de la orden para asociarlo; la evidencia queda visible al cliente.
 */
export function EvidenceUploadForm({ orderId, onSuccess, className }: EvidenceUploadFormProps) {
    const { subir, progress, isUploading, success, error, requestId, isOffline, reset } =
        useEvidenceUpload(orderId);
    const { showToast } = useToast();

    const fileRef = useRef<HTMLInputElement>(null);
    const presupuestoCargadoRef = useRef(false);
    const [archivo, setArchivo] = useState<File | null>(null);
    const [contexto, setContexto] = useState<ContextoEvidencia>('diagnostico');
    const [visibleCliente, setVisibleCliente] = useState(false);
    const [errorLocal, setErrorLocal] = useState('');
    const [presupuestoId, setPresupuestoId] = useState<string | null>(null);
    const [estadoPresupuesto, setEstadoPresupuesto] = useState<EstadoPresupuesto>('idle');

    const esPresupuesto = contexto === 'presupuesto';

    // En contexto presupuesto, la evidencia se asocia al presupuesto de la orden.
    // El ref evita re-disparar la carga cuando `estadoPresupuesto` cambia (si
    // estuviera en las dependencias, su cleanup cancelaría la petición en curso).
    useEffect(() => {
        if (!esPresupuesto || presupuestoCargadoRef.current) return;
        presupuestoCargadoRef.current = true;
        let active = true;
        setEstadoPresupuesto('loading');
        presupuestoService
            .getByOrder(orderId)
            .then((presupuesto) => {
                if (!active) return;
                setPresupuestoId(presupuesto ? presupuesto.id : null);
                setEstadoPresupuesto(presupuesto ? 'listo' : 'ausente');
            })
            .catch(() => {
                if (!active) return;
                setPresupuestoId(null);
                setEstadoPresupuesto('ausente');
            });
        return () => {
            active = false;
        };
    }, [esPresupuesto, orderId]);

    const limpiarResultado = () => {
        reset();
        setErrorLocal('');
    };

    const seleccionarArchivo = (evento: ChangeEvent<HTMLInputElement>) => {
        setArchivo(evento.target.files?.[0] ?? null);
        limpiarResultado();
    };

    const onSubmit = async (evento: FormEvent) => {
        evento.preventDefault();
        if (isUploading) return;

        if (!archivo) {
            setErrorLocal('Selecciona una foto o un video.');
            return;
        }
        if (!esContentTypeEvidenciaPermitido(archivo.type)) {
            setErrorLocal('Solo se permiten imágenes o videos.');
            return;
        }
        if (archivo.size > TAMANO_MAXIMO_EVIDENCIA_BYTES) {
            setErrorLocal(`El archivo supera el límite de ${formatBytes(TAMANO_MAXIMO_EVIDENCIA_BYTES)}.`);
            return;
        }
        if (esPresupuesto && estadoPresupuesto === 'loading') {
            setErrorLocal('Esperando el presupuesto de la orden...');
            return;
        }
        if (esPresupuesto && !presupuestoId) {
            setErrorLocal('Esta orden no tiene un presupuesto al que asociar la evidencia.');
            return;
        }

        setErrorLocal('');
        const evidencia = await subir({
            archivo,
            contexto,
            presupuestoId: esPresupuesto ? presupuestoId : null,
            visibleCliente: esPresupuesto ? true : visibleCliente,
        });
        if (evidencia) {
            showToast('Evidencia subida correctamente.', 'success');
            setArchivo(null);
            if (fileRef.current) fileRef.current.value = '';
            onSuccess?.(evidencia);
        }
    };

    const mensajeError = errorLocal || error;

    return (
        <form onSubmit={onSubmit} className={className} noValidate aria-label="Subir evidencia">
            <div className="grid gap-4 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm">
                    <span className="text-text-muted">Archivo (foto o video)</span>
                    <input
                        ref={fileRef}
                        type="file"
                        accept="image/*,video/*"
                        onChange={seleccionarArchivo}
                        className={INPUT_CLASS}
                        aria-invalid={!!errorLocal && !archivo}
                    />
                    {archivo && (
                        <span className="text-xs text-text-muted">
                            {archivo.name} · {formatBytes(archivo.size)}
                        </span>
                    )}
                </label>

                <label className="flex flex-col gap-1 text-sm">
                    <span className="text-text-muted">Contexto</span>
                    <select
                        value={contexto}
                        onChange={(evento) => {
                            setContexto(evento.target.value as ContextoEvidencia);
                            limpiarResultado();
                        }}
                        className={INPUT_CLASS}
                        disabled={isUploading}
                    >
                        {CONTEXTOS.map((valor) => (
                            <option key={valor} value={valor}>
                                {CONTEXTO_EVIDENCIA_LABEL[valor]}
                            </option>
                        ))}
                    </select>
                </label>
            </div>

            {esPresupuesto ? (
                <p className="mt-3 text-sm text-text-muted">
                    La evidencia del presupuesto se asocia automáticamente y siempre es visible para
                    el cliente.
                    {estadoPresupuesto === 'ausente' && (
                        <span className="block mt-1 text-status-yellow">
                            Esta orden no tiene un presupuesto registrado.
                        </span>
                    )}
                </p>
            ) : (
                <label className="mt-4 flex items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        checked={visibleCliente}
                        onChange={(evento) => setVisibleCliente(evento.target.checked)}
                        disabled={isUploading}
                    />
                    <span className="text-text-muted">Visible para el cliente</span>
                </label>
            )}

            {isUploading && (
                <div className="mt-4" aria-live="polite">
                    <div className="mb-1 flex items-center justify-between text-sm text-text-muted">
                        <span>Subiendo evidencia...</span>
                        <span>{progress}%</span>
                    </div>
                    <ProgressBar value={progress} className="mt-1" />
                </div>
            )}

            {success && !isUploading && (
                <Alert tone="success" className="mt-4">
                    Evidencia subida correctamente.
                </Alert>
            )}

            {mensajeError && !isUploading && (
                <Alert tone="error" className="mt-4">
                    {isOffline
                        ? 'Sin conexión: no se pudo subir la evidencia. Revisa tu red e inténtalo de nuevo.'
                        : mensajeError}
                    {requestId && (
                        <span className="block mt-1 font-mono text-xs opacity-80">
                            Referencia: {requestId}
                        </span>
                    )}
                </Alert>
            )}

            <Button
                type="submit"
                variant="primary"
                className="mt-4 inline-flex items-center gap-2"
                isLoading={isUploading}
                disabled={isUploading || !archivo}
            >
                <Upload className="h-4 w-4" aria-hidden />
                Subir evidencia
            </Button>
        </form>
    );
}