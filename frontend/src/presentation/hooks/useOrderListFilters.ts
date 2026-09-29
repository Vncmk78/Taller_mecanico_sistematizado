import { useMemo, useState } from 'react';
import type { Order } from '@/domain/entities/Order';

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

/**
 * Filtros y paginación del listado de órdenes, del lado cliente (la caché de
 * useOrderStore ya tiene todos los datos; MS2 no expone paginación server-side
 * todavía). Reutilizado por los 3 portales; cada página entrega la función que
 * arma el texto buscable de cada orden (patente/vehículo vienen de utilidades).
 */
export function useOrderListFilters(
    orders: Order[],
    searchableFields: (order: Order) => string
): UseOrderListFiltersResult {
    const [search, setSearch] = useState('');
    const [estadoCodigo, setEstadoCodigo] = useState<OrderEstadoFilter>('all');
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

    // Cambiar un filtro reinicia la paginación desde la primera página.
    const changeSearch = (value: string) => {
        setSearch(value);
        setPage(1);
    };
    const changeEstado = (value: OrderEstadoFilter) => {
        setEstadoCodigo(value);
        setPage(1);
    };

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
        setPage,
        pageSize,
        setPageSize,
        filteredOrders,
        pagedOrders,
        total,
        pageCount,
        rangeStart: total === 0 ? 0 : (safePage - 1) * pageSize + 1,
        rangeEnd: Math.min(safePage * pageSize, total),
    };
}