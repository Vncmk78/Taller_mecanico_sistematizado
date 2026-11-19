import { useEffect, useState } from 'react';

/**
 * Retardo por defecto de las búsquedas: el valor "debounced" tarda 300 ms en
 * alcanzar al valor inmediato del input.
 */
export const DEFAULT_DEBOUNCE_MS = 300;

/**
 * Devuelve `value` retrasado `delayMs` milisegundos.
 *
 * El input puede seguir usando el valor inmediato (responde a cada tecla),
 * mientras que el filtrado/consulta usa el valor retornado: así se evita
 * recalcular o consultar el servidor en cada pulsación.
 *
 * Con `delayMs <= 0` el valor se devuelve sin espera, útil en pruebas que
 * necesitan comportamiento síncrono.
 */
export function useDebouncedValue<T>(value: T, delayMs: number = DEFAULT_DEBOUNCE_MS): T {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        if (delayMs <= 0) return;
        const timer = setTimeout(() => setDebouncedValue(value), delayMs);
        return () => clearTimeout(timer);
    }, [value, delayMs]);

    return delayMs <= 0 ? value : debouncedValue;
}
