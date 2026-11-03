import type { Repuesto } from '@/domain/entities/Repuesto';

export type StockStatusKey = 'sin_stock' | 'critico' | 'bajo' | 'normal';

/** Filtro de la pantalla: los cuatro estados más "todos". */
export type StockFilter = 'todos' | StockStatusKey;

export interface StockStatus {
    key: StockStatusKey;
    label: string;
    className: string;
}

interface StockStatusMeta {
    label: string;
    className: string;
}

/**
 * Estilos por estado. Se usan los tokens de color del proyecto para que el
 * contraste sea el mismo que en el resto de badges (Alert, ErrorState, etc.).
 */
const META: Record<StockStatusKey, StockStatusMeta> = {
    sin_stock: {
        label: 'Sin stock',
        className: 'bg-status-red/10 text-status-red border border-status-red/40',
    },
    critico: {
        label: 'Crítico',
        className: 'bg-status-orange/10 text-status-orange border border-status-orange/40',
    },
    bajo: {
        label: 'Bajo',
        className: 'bg-status-yellow/10 text-status-yellow border border-status-yellow/40',
    },
    normal: {
        label: 'Normal',
        className: 'bg-status-green/10 text-status-green border border-status-green/40',
    },
};

/** Orden estable de las opciones del filtro (de más grave a menos grave). */
export const STOCK_STATUS_OPTIONS: ReadonlyArray<{ key: StockStatusKey; label: string }> = (
    ['sin_stock', 'critico', 'bajo', 'normal'] as const
).map((key) => ({ key, label: META[key].label }));

/**
 * Umbral aplicable: el particular del repuesto o, si no tiene, el general
 * vigente que ya resuelve el backend en `umbral_efectivo`. Un umbral en 0 o
 * negativo equivale a "sin umbral configurado".
 */
function getUmbral(repuesto: Repuesto): number | null {
    for (const valor of [repuesto.umbralEfectivo, repuesto.umbralParticular]) {
        if (valor != null && valor > 0) return valor;
    }
    return null;
}

function estado(key: StockStatusKey): StockStatus {
    return { key, ...META[key] };
}

/**
 * Estado visual del stock.
 *
 * - `sin_stock`: no queda ninguna unidad.
 * - `critico`: queda stock pero está en la mitad o menos del umbral.
 * - `bajo`: queda stock y está por debajo del umbral (estricto, igual que
 *   `bajo_umbral` del backend: `stock < umbral`).
 * - `normal`: en el umbral o por encima, o sin umbral configurado.
 *
 * "Crítico" es un subnivel visual de "Bajo": ambos están bajo el umbral, pero
 * el crítico exige atención inmediata.
 */
export function getStockStatus(repuesto: Repuesto): StockStatus {
    const stock = repuesto.stock ?? 0;
    if (stock <= 0) return estado('sin_stock');

    const umbral = getUmbral(repuesto);
    if (umbral == null) return estado('normal');

    if (stock < umbral) {
        return estado(stock <= umbral / 2 ? 'critico' : 'bajo');
    }

    return estado('normal');
}

export function getStockStatusLabel(status: StockStatusKey): string {
    return META[status].label;
}
