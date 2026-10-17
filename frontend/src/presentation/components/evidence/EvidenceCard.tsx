import { useEffect, useState } from 'react';
import { Eye, ImageOff, Play, RotateCw } from 'lucide-react';
import { contextoEvidenciaLabel, esImagen, esVideo, type Evidencia } from '@/domain/entities/Evidencia';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { Spinner } from '@/presentation/components/ui/Spinner';
import { formatBytes } from '@/presentation/utils/evidenceDisplay';
import { formatDateTime } from '@/presentation/utils/orderDisplay';

interface EvidenceCardProps {
    evidencia: Evidencia;
    /**
     * Se llama al pedir ver el archivo, con la URL prefirmada ya resuelta (null si
     * aún no se pudo obtener: el padre decide si abre o reintenta).
     */
    onPreview: (evidencia: Evidencia, url: string | null) => void;
}

/**
 * Tarjeta de una evidencia. Pide una URL prefirmada para mostrar la miniatura
 * (las URLs son efímeras y no se cachean). Si la URL falla, ofrece reintentar en
 * lugar de dejar la imagen rota.
 */
export function EvidenceCard({ evidencia, onPreview }: EvidenceCardProps) {
    const [url, setUrl] = useState<string | null>(null);
    const [fallo, setFallo] = useState(false);
    const [intento, setIntento] = useState(0);

    useEffect(() => {
        let active = true;
        (async () => {
            try {
                const resultado = await evidenciaService.getDownloadUrl(evidencia.id);
                if (!active) return;
                setUrl(resultado.url);
                setFallo(false);
            } catch {
                if (!active) return;
                setUrl(null);
                setFallo(true);
            }
        })();
        return () => {
            active = false;
        };
    }, [evidencia.id, intento]);

    const reintentar = () => {
        setFallo(false);
        setUrl(null);
        setIntento((n) => n + 1);
    };

    const cargando = url === null && !fallo;
    const imagen = esImagen(evidencia);
    const video = esVideo(evidencia);

    return (
        <div className="card p-0 overflow-hidden flex flex-col">
            <div className="relative aspect-video bg-bg-secondary flex items-center justify-center">
                {imagen && url && (
                    <img
                        src={url}
                        alt={evidencia.nombreOriginal}
                        loading="lazy"
                        className="w-full h-full object-cover"
                    />
                )}

                {video && url && (
                    <button
                        type="button"
                        onClick={() => onPreview(evidencia, url)}
                        aria-label={`Reproducir ${evidencia.nombreOriginal}`}
                        className="w-full h-full flex items-center justify-center bg-black/60 text-white border-none cursor-pointer"
                    >
                        <Play className="w-10 h-10" aria-hidden />
                    </button>
                )}

                {cargando && <Spinner className="w-6 h-6 text-text-muted" />}

                {fallo && (
                    <div className="flex flex-col items-center gap-2 text-text-muted p-4 text-center">
                        <ImageOff className="w-7 h-7" aria-hidden />
                        <p className="text-sm">No se pudo cargar el archivo.</p>
                        <button
                            type="button"
                            onClick={reintentar}
                            className="inline-flex items-center gap-2 text-primary-blue text-sm font-medium bg-transparent border-none cursor-pointer hover:underline"
                        >
                            <RotateCw className="w-4 h-4" aria-hidden /> Reintentar
                        </button>
                    </div>
                )}
            </div>

            <div className="p-4 flex flex-col gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-primary-blue">
                    {contextoEvidenciaLabel(evidencia.contexto)}
                </span>
                <p className="text-sm font-medium text-text-main truncate" title={evidencia.nombreOriginal}>
                    {evidencia.nombreOriginal}
                </p>
                <p className="text-xs text-text-muted">
                    {formatBytes(evidencia.tamanoBytes)} · {formatDateTime(evidencia.creadaEn)}
                </p>

                <button
                    type="button"
                    onClick={() => onPreview(evidencia, url)}
                    disabled={cargando}
                    aria-label={`Ver ${evidencia.nombreOriginal}`}
                    className="mt-1 inline-flex items-center justify-center gap-2 bg-surface border border-border-custom text-primary-blue py-2 rounded-lg text-sm hover:bg-bg-secondary transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Eye className="w-4 h-4" aria-hidden /> Ver
                </button>
            </div>
        </div>
    );
}
