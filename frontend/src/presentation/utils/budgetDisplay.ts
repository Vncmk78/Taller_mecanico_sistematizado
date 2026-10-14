import type { EfectoEnOrden } from '@/domain/entities/Presupuesto';

/** Formato monetario chileno sin decimales: 38990 -> "$38.990". */
export function formatMoneyCLP(value: number): string {
    return new Intl.NumberFormat('es-CL', {
        style: 'currency',
        currency: 'CLP',
        maximumFractionDigits: 0,
    }).format(value);
}

export const EFECTO_EN_ORDEN_LABEL: Record<EfectoEnOrden, string> = {
    esperando_aprobacion: 'Esperando aprobación de presupuesto',
    en_reparacion: 'En reparación',
    esperando_repuestos: 'Esperando repuestos',
    cancelado: 'Servicio cancelado',
};
