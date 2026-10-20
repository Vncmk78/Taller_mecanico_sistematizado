import { CONTEXTO_EVIDENCIA_LABEL, type Evidencia } from '@/domain/entities/Evidencia';
import {
    contarPorContexto,
    contextosPresentes,
    type ContextoFiltro,
} from '@/presentation/utils/evidenceDisplay';

interface EvidenceContextFilterProps {
    evidencias: Evidencia[];
    /** Selección vigente (controlada por la vista). */
    contexto: ContextoFiltro;
    onChange: (contexto: ContextoFiltro) => void;
    className?: string;
}

/**
 * Chips para filtrar la galería por contexto oficial (Diagnóstico, Presupuesto,
 * Reparación, Resultado final) con el conteo de archivos de cada uno. Si la
 * lista solo cubre un contexto no hay nada que filtrar y no se renderiza.
 */
export function EvidenceContextFilter({
    evidencias,
    contexto,
    onChange,
    className = '',
}: EvidenceContextFilterProps) {
    const presentes = contextosPresentes(evidencias);
    if (presentes.length < 2) return null;

    const conteo = contarPorContexto(evidencias);

    const chipClass = (activo: boolean) =>
        `inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium border transition-colors cursor-pointer ${
            activo
                ? 'bg-primary-blue border-primary-blue text-white'
                : 'bg-surface border-border-custom text-text-muted hover:text-text-main hover:border-primary-blue'
        }`;

    return (
        <div
            role="group"
            aria-label="Filtrar evidencia por contexto"
            className={`flex flex-wrap items-center gap-2 ${className}`}
        >
            <span className="text-sm text-text-muted mr-1">Filtrar por contexto:</span>
            <button
                type="button"
                aria-pressed={contexto === 'todos'}
                className={chipClass(contexto === 'todos')}
                onClick={() => onChange('todos')}
            >
                Todos ({evidencias.length})
            </button>
            {presentes.map((contextoActual) => (
                <button
                    key={contextoActual}
                    type="button"
                    aria-pressed={contexto === contextoActual}
                    className={chipClass(contexto === contextoActual)}
                    onClick={() => onChange(contextoActual)}
                >
                    {CONTEXTO_EVIDENCIA_LABEL[contextoActual]} ({conteo[contextoActual]})
                </button>
            ))}
        </div>
    );
}
