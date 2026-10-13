import { useEffect } from 'react';
import { Download, X } from 'lucide-react';
import { contextoEvidenciaLabel, esImagen, esVideo, type Evidencia } from '@/domain/entities/Evidencia';
import { Button } from '@/presentation/components/ui/Button';
import { formatBytes } from '@/presentation/utils/evidenceDisplay';
import { formatDateTime } from '@/presentation/utils/orderDisplay';

interface EvidencePreviewDialogProps {
    evidencia: Evidencia;
    /** URL prefirmada vigente del archivo. */
    url: string;
    onClose: () => void;
}

/**
 * Vista previa a pantalla completa de una evidencia. Usa la URL prefirmada ya
 * obtenida; el usuario puede abrir el archivo original para descargarlo.
 */
export function EvidencePreviewDialog({ evidencia, url, onClose }: EvidencePreviewDialogProps) {
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [onClose]);

    const abrirOriginal = () => {
        window.open(url, '_blank', 'noopener,noreferrer');
    };

    return (
        <div
            className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 animate-fade-in"
            onMouseDown={(e) => {
                if (e.target === e.currentTarget) onClose();
            }}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-label={`Vista previa de ${evidencia.nombreOriginal}`}
                className="card relative w-full max-w-[760px] p-5"
            >
                <button
                    type="button"
                    aria-label="Cerrar"
                    onClick={onClose}
                    className="absolute right-4 top-4 z-10 text-text-muted hover:text-text-main bg-transparent border-none cursor-pointer"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="rounded-xl overflow-hidden bg-bg-secondary flex items-center justify-center max-h-[65vh]">
                    {esImagen(evidencia) && (
                        <img
                            src={url}
                            alt={evidencia.nombreOriginal}
                            className="max-h-[65vh] w-auto object-contain"
                        />
                    )}
                    {esVideo(evidencia) && (
                        <video src={url} controls autoPlay className="max-h-[65vh] w-full" />
                    )}
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mt-4">
                    <div className="min-w-0">
                        <p className="text-text-main font-medium truncate">{evidencia.nombreOriginal}</p>
                        <p className="text-sm text-text-muted">
                            {contextoEvidenciaLabel(evidencia.contexto)} · {formatBytes(evidencia.tamanoBytes)} ·{' '}
                            {formatDateTime(evidencia.creadaEn)}
                        </p>
                    </div>
                    <Button
                        type="button"
                        variant="primary"
                        onClick={abrirOriginal}
                        className="shrink-0 inline-flex items-center gap-2"
                    >
                        <Download className="w-4 h-4" aria-hidden /> Descargar
                    </Button>
                </div>
            </div>
        </div>
    );
}
