import { useEffect, useRef, type KeyboardEvent } from 'react';

const FOCUSABLE_SELECTOR = [
    'a[href]',
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * Accesibilidad básica de un diálogo modal: mueve el foco al abrirlo, lo encierra
 * dentro mientras está abierto (Tab / Shift+Tab) y lo devuelve al elemento que lo
 * abrió al cerrarlo. El contenedor debe recibir `ref`, `tabIndex={-1}` y
 * `onKeyDown` retornados por el hook; el cierre con Escape y el clic en el fondo
 * siguen siendo responsabilidad del diálogo.
 */
export function useDialogFocus<T extends HTMLElement>(active = true) {
    const ref = useRef<T | null>(null);

    useEffect(() => {
        if (!active) return;
        const container = ref.current;
        const previous = document.activeElement as HTMLElement | null;

        container?.focus({ preventScroll: true });

        return () => {
            if (previous && typeof previous.focus === 'function') {
                previous.focus({ preventScroll: true });
            }
        };
    }, [active]);

    const handleKeyDown = (event: KeyboardEvent) => {
        if (event.key !== 'Tab') return;
        const container = ref.current;
        if (!container) return;

        const focusables = Array.from(
            container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
        ).filter((element) => element.tabIndex !== -1);

        if (focusables.length === 0) {
            event.preventDefault();
            return;
        }

        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const activeElement = document.activeElement;

        if (event.shiftKey && (activeElement === first || activeElement === container)) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && (activeElement === last || activeElement === container)) {
            event.preventDefault();
            first.focus();
        }
    };

    return { ref, handleKeyDown };
}
