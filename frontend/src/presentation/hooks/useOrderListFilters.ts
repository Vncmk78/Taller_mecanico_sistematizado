import { useCallback, useMemo, useState } from 'react';
import type { Order } from '@/domain/entities/Order';
import { parseNumberOrDefault, parseStringOrDefault, serializeNumber, serializeString, useUrlState } from '@/presentation/hooks/useUrlState';
import { usePersistentState } from '@/presentation/hooks/usePersistentState';

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
    /** Limpia filtros/paginación persistidos (URL o localStorage). */
    resetFilters: () => void;
}

interface UseOrderListFiltersOptions {
    /** Sincroniza search, estado, page y pageSize con la URL (query params). */
    syncWithUrl?: boolean;
    /** Clave base para los query params. Útil si hay varios listados en la misma ruta. */
    urlKeyPrefix?: string;
    /** Persiste filtros en localStorage cuando syncWithUrl=false. */
    persistInStorage?: boolean;
    /** Clave para localStorage/sessionStorage. */
    storageKey?: string;
    /** Tipo de storage al persistir localmente. */
    storageType?: 'local' | 'session';
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
    const {
        syncWithUrl = false,
        urlKeyPrefix = '',
        persistInStorage = true,
        storageKey = 'tallerconect:orders-filters',
        storageType = 'local',
    } = options;

    const searchKey = `${urlKeyPrefix}q`;
    const estadoKey = `${urlKeyPrefix}estado`;
    const pageKey = `${urlKeyPrefix}page`;
    const pageSizeKey = `${urlKeyPrefix}pageSize`;

    const [searchState, setSearchState] = useState('');
    const [estadoState, setEstadoState] = useState<OrderEstadoFilter>('all');
    const [pageState, setPageState] = useState(1);
    const [pageSizeState, setPageSizeState] = useState(DEFAULT_PAGE_SIZE);

    const [searchStored, setSearchStored] = usePersistentState<string>(`${storageKey}:search`, '', storageType);
    const [estadoStored, setEstadoStored] = usePersistentState<OrderEstadoFilter>(`${storageKey}:estado`, 'all', storageType);
    const [pageStored, setPageStored] = usePersistentState<number>(`${storageKey}:page`, 1, storageType);
    const [pageSizeStored, setPageSizeStored] = usePersistentState<number>(`${storageKey}:pageSize`, DEFAULT_PAGE_SIZE, storageType);

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

    const search = syncWithUrl ? searchUrl : persistInStorage ? searchStored : searchState;
    const estadoCodigo = syncWithUrl ? estadoUrl : persistInStorage ? estadoStored : estadoState;
    const page = syncWithUrl ? pageUrl : persistInStorage ? pageStored : pageState;
    const pageSize = syncWithUrl ? pageSizeUrl : persistInStorage ? pageSizeStored : pageSizeState;

    // Cambiar un filtro reinicia la paginación desde la primera página.
    const changeSearch = useCallback(
        (value: string) => {
            if (syncWithUrl) {
                setSearchUrl(value);
                setPageUrl(1);
            } else if (persistInStorage) {
                setSearchStored(value);
                setPageStored(1);
            } else {
                setSearchState(value);
                setPageState(1);
            }
        },
        [syncWithUrl, persistInStorage, setSearchUrl, setPageUrl, setSearchStored, setPageStored]
    );
    const changeEstado = useCallback(
        (value: OrderEstadoFilter) => {
            if (syncWithUrl) {
                setEstadoUrl(value);
                setPageUrl(1);
            } else if (persistInStorage) {
                setEstadoStored(value);
                setPageStored(1);
            } else {
                setEstadoState(value);
                setPageState(1);
            }
        },
        [syncWithUrl, persistInStorage, setEstadoUrl, setPageUrl, setEstadoStored, setPageStored]
    );

    const setPageSafe = useCallback(
        (nextPage: number) => {
            if (syncWithUrl) {
                setPageUrl(nextPage);
            } else if (persistInStorage) {
                setPageStored(nextPage);
            } else {
                setPageState(nextPage);
            }
        },
        [syncWithUrl, persistInStorage, setPageUrl, setPageStored]
    );
    const setPageSizeSafe = useCallback(
        (nextSize: number) => {
            const size = (ORDER_PAGE_SIZES as readonly number[]).includes(nextSize) ? nextSize : DEFAULT_PAGE_SIZE;
            if (syncWithUrl) {
                setPageSizeUrl(size);
                setPageUrl(1);
            } else if (persistInStorage) {
                setPageSizeStored(size);
                setPageStored(1);
            } else {
                setPageSizeState(size);
                setPageState(1);
            }
        },
        [syncWithUrl, persistInStorage, setPageSizeUrl, setPageUrl, setPageSizeStored, setPageStored]
    );

    const resetFilters = useCallback(() => {
        if (syncWithUrl) {
            setSearchUrl('');
            setEstadoUrl('all');
            setPageUrl(1);
            setPageSizeUrl(DEFAULT_PAGE_SIZE);
            return;
        }
        if (persistInStorage) {
            setSearchStored('');
            setEstadoStored('all');
            setPageStored(1);
            setPageSizeStored(DEFAULT_PAGE_SIZE);
            return;
        }
        setSearchState('');
        setEstadoState('all');
        setPageState(1);
        setPageSizeState(DEFAULT_PAGE_SIZE);
    }, [syncWithUrl, persistInStorage, setSearchUrl, setEstadoUrl, setPageUrl, setPageSizeUrl, setSearchStored, setEstadoStored, setPageStored, setPageSizeStored]);

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
        resetFilters,
    };
}