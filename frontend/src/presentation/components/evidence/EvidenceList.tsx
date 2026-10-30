import { useEffect, useState } from 'react';
import { Download, Eye, FileVideo, Image, ImageOff } from 'lucide-react';
import { contextoEvidenciaLabel, esImagen, esVideo, type Evidencia } from '@/domain/entities/Evidencia';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';

const ESTADO_LABEL: Record<Evidencia['estado'], string> = {
    confirmada: 'Confirmada',
    pendiente: 'Pendiente',
    anulada: 'Anulada',
};

const TIPO_LABEL: Record<Evidencia['tipoArchivo'], string> = {
    foto: 'Foto',
    video: 'Video',
};
import { Spinner } from '@/presentation/components/ui/Spinner';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { Alert } from '@/presentation/components/ui/Alert';
import { formatBytes } from '@/presentation/utils/evidenceDisplay';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { EvidencePreviewDialog } from './EvidencePreviewDialog';

interface EvidenceListProps {
    ordenId: string;
    refreshKey?: number;
    className?: string;
}

interface EnVista {
    evidencia: Evidencia;
    url: string;
}

function getEstadoBadgeClass(estado: Evidencia['estado']) {
    if (estado === 'confirmada') {
        return 'bg-status-green/10 text-status-green border border-status-green/30';
    }
    if (estado === 'pendiente') {
        return 'bg-status-yellow/10 text-status-yellow border border-status-yellow/30';
    }
    return 'bg-status-red/10 text-status-red border border-status-red/30';
}

function getVisibilidadLabel(visible: boolean) {
    return visible ? 'Visible para el cliente' : 'No visible para el cliente';
}

export function EvidenceList({ ordenId, refreshKey = 0, className = '' }: EvidenceListProps) {
    const [evidencias, setEvidencias] = useState<Evidencia[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [vista, setVista] = useState<EnVista | null>(null);
    const [descargandoId, setDescargandoId] = useState<string | null>(null);

    const cargar = async () => {
        setLoading(true);
        setError(null);
        try {
            const datos = await evidenciaService.getByOrder(ordenId);
            setEvidencias(datos);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'No se pudieron cargar las evidencias.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        cargar();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ordenId, refreshKey]);

    const ver = async (evidencia: Evidencia) => {
        try {
            const resultado = await evidenciaService.getDownloadUrl(evidencia.id);
            setVista({ evidencia, url: resultado.url });
        } catch {
            setError('No se pudo obtener la URL de previsualización.');
        }
    };

    const descargar = async (evidencia: Evidencia) => {
        setDescargandoId(evidencia.id);
        try {
            const resultado = await evidenciaService.getDownloadUrl(evidencia.id);
            const link = document.createElement('a');
            link.href = resultado.url;
            link.download = evidencia.nombreOriginal;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch {
            setError('No se pudo descargar la evidencia.');
        } finally {
            setDescargandoId(null);
        }
    };

    return (
        <div className={className}>
            {error && (
                <Alert tone="error" className="mb-4" action={<RetryButton tone="error" onClick={cargar} />}>
                    {error}
                </Alert>
            )}

            {loading ? (
                <div className="flex items-center gap-2 text-text-muted">
                    <Spinner className="h-5 w-5" /> Cargando evidencias...
                </div>
            ) : evidencias.length === 0 ? (
                <EmptyState
                    icon={ImageOff}
                    title="Aún no hay evidencia multimedia"
                    description="Sube una foto o un video del diagnóstico, la reparación o el resultado final."
                />
            ) : (
                <div className="flex flex-col gap-3">
                    {evidencias.map((evidencia) => {
                        const esImg = esImagen(evidencia);
                        const esVid = esVideo(evidencia);

                        return (
                            <div
                                key={evidencia.id}
                                className="card p-4 flex flex-col sm:flex-row sm:items-center gap-4"
                            >
                                <div className="w-16 h-16 rounded-lg bg-bg-secondary flex items-center justify-center flex-shrink-0">
                                    {esImg && <Image className="w-6 h-6 text-text-muted" aria-hidden />}
                                    {esVid && <FileVideo className="w-6 h-6 text-text-muted" aria-hidden />}
                                    {!esImg && !esVid && <ImageOff className="w-6 h-6 text-text-muted" aria-hidden />}
                                </div>

                                <div className="flex-1 min-w-0">
                                    <div className="flex flex-wrap items-center gap-2 mb-1">
                                        <span className="text-sm font-medium text-text-main truncate">
                                            {evidencia.nombreOriginal}
                                        </span>
                                        <span
                                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${getEstadoBadgeClass(
                                                evidencia.estado
                                            )}`}
                                        >
                                            {ESTADO_LABEL[evidencia.estado]}
                                        </span>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                                        <span>{contextoEvidenciaLabel(evidencia.contexto)}</span>
                                        <span>·</span>
                                        <span>{TIPO_LABEL[evidencia.tipoArchivo]}</span>
                                        <span>·</span>
                                        <span>{formatBytes(evidencia.tamanoBytes)}</span>
                                        <span>·</span>
                                        <span>{formatDateTime(evidencia.creadaEn)}</span>
                                        <span>·</span>
                                        <span>{getVisibilidadLabel(evidencia.visibleCliente)}</span>
                                    </div>
                                </div>

                                <div className="flex items-center gap-2">
                                    <button
                                        type="button"
                                        onClick={() => ver(evidencia)}
                                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border-custom text-sm text-primary-blue hover:bg-bg-secondary transition-colors"
                                    >
                                        <Eye className="w-4 h-4" aria-hidden /> Ver
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => descargar(evidencia)}
                                        disabled={descargandoId === evidencia.id}
                                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border-custom text-sm text-text-main hover:bg-bg-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <Download className="w-4 h-4" aria-hidden />
                                        {descargandoId === evidencia.id ? 'Descargando...' : 'Descargar'}
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {vista && (
                <EvidencePreviewDialog
                    evidencia={vista.evidencia}
                    url={vista.url}
                    onClose={() => setVista(null)}
                />
            )}
        </div>
    );
}
