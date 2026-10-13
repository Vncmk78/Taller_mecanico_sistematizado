import { useState } from 'react';
import type { Evidencia } from '@/domain/entities/Evidencia';
import { EvidenceCard } from '@/presentation/components/evidence/EvidenceCard';
import { EvidencePreviewDialog } from '@/presentation/components/evidence/EvidencePreviewDialog';

interface EvidenceGalleryProps {
    evidencias: Evidencia[];
}

interface EnVista {
    evidencia: Evidencia;
    url: string;
}

/** Grilla de evidencias con vista previa compartida. */
export function EvidenceGallery({ evidencias }: EvidenceGalleryProps) {
    const [vista, setVista] = useState<EnVista | null>(null);

    const abrir = (evidencia: Evidencia, url: string | null) => {
        if (url) setVista({ evidencia, url });
    };

    return (
        <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {evidencias.map((evidencia) => (
                    <EvidenceCard key={evidencia.id} evidencia={evidencia} onPreview={abrir} />
                ))}
            </div>

            {vista && (
                <EvidencePreviewDialog
                    evidencia={vista.evidencia}
                    url={vista.url}
                    onClose={() => setVista(null)}
                />
            )}
        </>
    );
}
