import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { DEFAULT_PAGE_SIZE, PAGE_SIZES } from '@/presentation/constants/pagination';

interface UseClientPaginationOptions {
    /** Tamaños ofrecidos por el selector. Por defecto 6/12/24. */
    pageSizes?: readonly number[];
    /** Tamaño inicial. Debe pertenecer a `pageSizes`. */
    defaultPageSize?: number;
    /**
     * Valores cuyo cambio reinicia la página a 1 (p. ej. la búsqueda ya
     * debounced). No reinicia en el primer render para respetar la página
     * inicial.
     */
    resetDeps?: readonly unknown[];
}

interface UseClientPaginationResult<T> {
    page: number;
    setPage: (page: number) => void;
    pageSize: number;
    setPageSize: (size: number) => void;
    /** Página actual de `items` lista para renderizar. */
    pageItems: T[];
    total: number;
    pageCount: number;
    rangeStart: number;
    rangeEnd: number;
    /** Vuelve a la primera página sin tocar el tamaño. */
    resetPage: () => void;
}

/**
 * Paginación del lado cliente para listados operativos.
 *
 * Recibe la colección ya filtrada por la página y devuelve solo la página
 * visible. Si el filtro reduce el total, la página se recorta automáticamente
 * para no quedar fuera de rango. El estado vive en memoria: los listados
 * operativos no dependen de la URL y así cada pantalla conserva su propio
 * estado sin colisiones entre portales.
 */
export function useClientPagination<T>(
    items: readonly T[],
    options: UseClientPaginationOptions = {}
): UseClientPaginationResult<T> {
    const {
        pageSizes = PAGE_SIZES,
        defaultPageSize = DEFAULT_PAGE_SIZE,
        resetDeps = [],
    } = options;

    const [pageState, setPageState] = useState(1);
    const [pageSizeState, setPageSizeState] = useState(defaultPageSize);

    const total = items.length;
    const pageCount = Math.max(1, Math.ceil(total / pageSizeState));
    const page = Math.min(Math.max(1, pageState), pageCount);

    const setPage = useCallback((nextPage: number) => {
        setPageState(Number.isFinite(nextPage) ? Math.max(1, Math.trunc(nextPage)) : 1);
    }, []);

    const setPageSize = useCallback(
        (nextSize: number) => {
            const size = (pageSizes as readonly number[]).includes(nextSize)
                ? nextSize
                : defaultPageSize;
            setPageSizeState(size);
            setPageState(1);
        },
        [pageSizes, defaultPageSize]
    );

    const resetPage = useCallback(() => setPageState(1), []);

    // Reinicia al cambiar filtros, pero no en el montaje inicial.
    const resetKey = resetDeps.map((value) => String(value)).join('\u0000');
    const firstRender = useRef(true);
    useEffect(() => {
        if (firstRender.current) {
            firstRender.current = false;
            return;
        }
        setPageState(1);
    }, [resetKey]);

    const pageItems = useMemo(
        () => items.slice((page - 1) * pageSizeState, page * pageSizeState),
        [items, page, pageSizeState]
    );

    return {
        page,
        setPage,
        pageSize: pageSizeState,
        setPageSize,
        pageItems,
        total,
        pageCount,
        rangeStart: total === 0 ? 0 : (page - 1) * pageSizeState + 1,
        rangeEnd: Math.min(page * pageSizeState, total),
        resetPage,
    };
}
