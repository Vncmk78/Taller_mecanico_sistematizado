import { useCallback, useMemo, useState } from 'react';
import type { Order } from '@/domain/entities/Order';
import { parseNumberOrDefault, parseStringOrDefault, serializeNumber, serializeString, useUrlState } from '@/presentation/hooks/useUrlState';

export type OrderEstadoFilter = number | 'all';

export const ORDER_PAGE_SIZES = [6, 12, 24] as const;

const DEFAULT_PAGE_SIZE = 6;

interface UseOrderListFiltersResult {
    search: string;
    setSearch: (value: string) => void;
    estadoCodigo: OrderEstadoFilter;
    setEstadoCodigo: (value: OrderEstadoFilter) => void;
    page: number;
    setPage: (page: number) => void;
    pageSize: number;
    setPageSize: (size: number) => void;
    /** Órdenes que pasan los filtros (búsqueda + estado), ordenadas por actualización más reciente. */
    filteredOrders: Order[];
    /** Página actual de filteredOrders para renderizar. */
    pagedOrders: Order[];
    total: number;
    pageCount: number;
    rangeStart: number;
    rangeEnd: number;
}

interface UseOrderListFiltersOptions {
    /** Sincroniza search, estado, page y pageSize con la URL (query params). */
    syncWithUrl?: boolean;
    /** Clave base para los query params. Útil si hay varios listados en la misma ruta. */
    urlKeyPrefix?: string;
}

/**
 * Filtros y paginación del listado de órdenes, del lado cliente (la caché de
 * useOrderStore ya tiene todos los datos; MS2 no expone paginación server-side
 * todavía). Reutilizado por los 3 portales; cada página entrega la función que
 * arma el texto buscable de cada orden (patente/vehículo vienen de utilidades).
 */
export function useOrderListFilters(
    orders: Order[],
    searchableFields: (order: Order) => string,
    options: UseOrderListFiltersOptions = {}
): UseOrderListFiltersResult {
    const { syncWithUrl = false, urlKeyPrefix = '' } = options;

    const searchKey = `${urlKeyPrefix}q`;
    const estadoKey = `${urlKeyPrefix}estado`;
    const pageKey = `${urlKeyPrefix}page`;
    const pageSizeKey = `${urlKeyPrefix}pageSize`;

    const [searchState, setSearchState] = useState('');
    const [estadoState, setEstadoState] = useState<OrderEstadoFilter>('all');
    const [pageState, setPageState] = useState(1);
    const [pageSizeState, setPageSizeState] = useState(DEFAULT_PAGE_SIZE);

    const [searchUrl, setSearchUrl] = useUrlState(searchKey, {
        defaultValue: '',
        parse: parseStringOrDefault(''),
        serialize: serializeString,
        replace: true,
    });
    const [estadoUrl, setEstadoUrl] = useUrlState<OrderEstadoFilter>(estadoKey, {
        defaultValue: 'all',
        parse: (raw) => {
            if (raw === null || raw === '' || raw === 'all') return 'all';
            const parsed = Number(raw);
            if (Number.isNaN(parsed)) return 'all';
            return parsed;
        },
        serialize: (value) => {
            if (value === 'all') return null;
            return String(value);
        },
        replace: true,
    });
    const [pageUrl, setPageUrl] = useUrlState(pageKey, {
        defaultValue: 1,
        parse: parseNumberOrDefault(1),
        serialize: serializeNumber,
        replace: true,
    });
    const [pageSizeUrl, setPageSizeUrl] = useUrlState(pageSizeKey, {
        defaultValue: DEFAULT_PAGE_SIZE,
        parse: (raw) => {
            const parsed = parseNumberOrDefault(DEFAULT_PAGE_SIZE)(raw);
            if ((ORDER_PAGE_SIZES as readonly number[]).includes(parsed)) return parsed;
            return DEFAULT_PAGE_SIZE;
        },
        serialize: (value) => {
            if (value === DEFAULT_PAGE_SIZE) return null;
            if ((ORDER_PAGE_SIZES as readonly number[]).includes(value)) return String(value);
            return null;
        },
        replace: true,
    });

    const search = syncWithUrl ? searchUrl : searchState;
    const estadoCodigo = syncWithUrl ? estadoUrl : estadoState;
    const page = syncWithUrl ? pageUrl : pageState;
    const pageSize = syncWithUrl ? pageSizeUrl : pageSizeState;

    // Cambiar un filtro reinicia la paginación desde la primera página.
    const changeSearch = useCallback(
        (value: string) => {
            if (syncWithUrl) {
                setSearchUrl(value);
                setPageUrl(1);
            } else {
                setSearchState(value);
                setPageState(1);
            }
        },
        [syncWithUrl, setSearchUrl, setPageUrl]
    );
    const changeEstado = useCallback(
        (value: OrderEstadoFilter) => {
            if (syncWithUrl) {
                setEstadoUrl(value);
                setPageUrl(1);
            } else {
                setEstadoState(value);
                setPageState(1);
            }
        },
        [syncWithUrl, setEstadoUrl, setPageUrl]
    );

    const setPageSafe = useCallback(
        (nextPage: number) => {
            if (syncWithUrl) {
                setPageUrl(nextPage);
            } else {
                setPageState(nextPage);
            }
        },
        [syncWithUrl, setPageUrl]
    );
    const setPageSizeSafe = useCallback(
        (nextSize: number) => {
            if (syncWithUrl) {
                const size = (ORDER_PAGE_SIZES as readonly number[]).includes(nextSize) ? nextSize : DEFAULT_PAGE_SIZE;
                setPageSizeUrl(size);
                setPageUrl(1);
            } else {
                const size = (ORDER_PAGE_SIZES as readonly number[]).includes(nextSize) ? nextSize : DEFAULT_PAGE_SIZE;
                setPageSizeState(size);
                setPageState(1);
            }
        },
        [syncWithUrl, setPageSizeUrl, setPageUrl]
    );

    const filteredOrders = useMemo(() => {
        const term = search.trim().toLowerCase();
        return orders
            .filter((o) => (estadoCodigo === 'all' ? true : o.estadoCodigo === estadoCodigo))
            .filter((o) => (term ? searchableFields(o).toLowerCase().includes(term) : true))
            .sort((a, b) => (a.actualizadoEn < b.actualizadoEn ? 1 : -1));
    }, [orders, search, estadoCodigo, searchableFields]);

    const total = filteredOrders.length;
    const pageCount = Math.max(1, Math.ceil(total / pageSize));
    // Si la página quedó fuera de rango (p. ej. al crecer pageSize), se ajusta.
    const safePage = Math.min(page, pageCount);

    const pagedOrders = useMemo(
        () => filteredOrders.slice((safePage - 1) * pageSize, safePage * pageSize),
        [filteredOrders, safePage, pageSize]
    );

    return {
        search,
        setSearch: changeSearch,
        estadoCodigo,
        setEstadoCodigo: changeEstado,
        page: safePage,
        setPage: setPageSafe,
        pageSize,
        setPageSize: setPageSizeSafe,
        filteredOrders,
        pagedOrders,
        total,
        pageCount,
        rangeStart: total === 0 ? 0 : (safePage - 1) * pageSize + 1,
        rangeEnd: Math.min(safePage * pageSize, total),
    };
}