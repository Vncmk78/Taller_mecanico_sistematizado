import { type ContextoEvidencia, type Evidencia } from '@/domain/entities/Evidencia';

/** Selección de la galería: un contexto concreto o todo el conjunto. */
export type ContextoFiltro = ContextoEvidencia | 'todos';

/** Los cuatro contextos oficiales, en el orden de la sistematización. */
export const CONTEXTOS_EVIDENCIA: readonly ContextoEvidencia[] = [
    'diagnostico',
    'presupuesto',
    'reparacion',
    'resultado_final',
];

/** Contextos que aparecen en la lista, en el orden oficial (para chips de filtro). */
export function contextosPresentes(evidencias: Evidencia[]): ContextoEvidencia[] {
    const presentes = new Set(evidencias.map((evidencia) => evidencia.contexto));
    return CONTEXTOS_EVIDENCIA.filter((contexto) => presentes.has(contexto));
}

/** Cuántas evidencias hay en cada contexto (los ausentes quedan en 0). */
export function contarPorContexto(evidencias: Evidencia[]): Record<ContextoEvidencia, number> {
    const conteo: Record<ContextoEvidencia, number> = {
        diagnostico: 0,
        presupuesto: 0,
        reparacion: 0,
        resultado_final: 0,
    };
    for (const evidencia of evidencias) {
        conteo[evidencia.contexto] += 1;
    }
    return conteo;
}

/** Sublista de la galería para el contexto seleccionado (`todos` = sin filtrar). */
export function filtrarPorContexto(evidencias: Evidencia[], contexto: ContextoFiltro): Evidencia[] {
    if (contexto === 'todos') return evidencias;
    return evidencias.filter((evidencia) => evidencia.contexto === contexto);
}

/**
 * Evidencias del contexto `presupuesto` de un presupuesto lógico puntual, para
 * mostrarlas junto al presupuesto (4.4 de la sistematización). El backend solo
 * envía `presupuestoId` en ese contexto.
 */
export function evidenciasDelPresupuesto(evidencias: Evidencia[], presupuestoId: string): Evidencia[] {
    return evidencias.filter(
        (evidencia) => evidencia.contexto === 'presupuesto' && evidencia.presupuestoId === presupuestoId
    );
}

/** Tamaño de archivo legible en español, sin decimales para bytes. */
export function formatBytes(bytes: number): string {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / 1024 ** i;
    return `${value.toLocaleString('es-CL', { maximumFractionDigits: i === 0 ? 0 : 1 })} ${units[i]}`;
}
