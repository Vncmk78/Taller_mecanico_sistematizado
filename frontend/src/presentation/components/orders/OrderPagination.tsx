import { ChevronLeft, ChevronRight } from 'lucide-react';
import { ORDER_PAGE_SIZES } from '@/presentation/hooks/useOrderListFilters';

interface OrderPaginationProps {
    page: number;
    pageCount: number;
    onPageChange: (page: number) => void;
    pageSize: number;
    onPageSizeChange: (size: number) => void;
    rangeStart: number;
    rangeEnd: number;
    total: number;
    className?: string;
}

/** Lista de páginas a mostrar, con elipsis cuando hay muchas. */
function pageItems(pageCount: number, current: number): Array<number | 'ellipsis'> {
    if (pageCount <= 7) {
        return Array.from({ length: pageCount }, (_, i) => i + 1);
    }
    const items: Array<number | 'ellipsis'> = [1];
    if (current > 3) items.push('ellipsis');
    for (let i = Math.max(2, current - 1); i <= Math.min(pageCount - 1, current + 1); i += 1) {
        items.push(i);
    }
    if (current < pageCount - 2) items.push('ellipsis');
    items.push(pageCount);
    return [...new Set(items)];
}

const pageButtonClass = [
    'px-3 py-1.5 rounded-md text-sm transition-colors',
    'bg-white/10 hover:bg-white/20',
    'disabled:opacity-40 disabled:cursor-not-allowed',
].join(' ');

/**
 * Paginación clásica del listado de órdenes: anterior/siguiente, páginas
 * numeradas, selector de tamaño (6/12/24) y "Mostrando X–Y de N". Se oculta
 * cuando el total cabe en una sola página.
 */
export function OrderPagination({
    page,
    pageCount,
    onPageChange,
    pageSize,
    onPageSizeChange,
    rangeStart,
    rangeEnd,
    total,
    className = '',
}: OrderPaginationProps) {
    if (total <= pageSize) return null;

    const items = pageItems(pageCount, page);

    return (
        <div className={`flex flex-wrap items-center justify-between gap-4 ${className}`}>
            <p className="text-sm text-text-muted">
                Mostrando {rangeStart}–{rangeEnd} de {total} órdenes
            </p>

            <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-sm text-text-muted">
                    <span className="whitespace-nowrap">Mostrar</span>
                    <select
                        value={pageSize}
                        onChange={(e) => onPageSizeChange(Number(e.target.value))}
                        aria-label="Órdenes por página"
                        className="bg-black/40 border border-border-custom rounded-lg px-3 py-1.5 text-white text-sm outline-none focus:border-primary-red"
                    >
                        {ORDER_PAGE_SIZES.map((size) => (
                            <option key={size} value={size}>
                                {size}
                            </option>
                        ))}
                    </select>
                </label>

                <nav aria-label="Paginación de órdenes" className="flex items-center gap-1">
                    <button
                        type="button"
                        onClick={() => onPageChange(page - 1)}
                        disabled={page <= 1}
                        className={`inline-flex items-center gap-1 ${pageButtonClass}`}
                    >
                        <ChevronLeft className="w-4 h-4" aria-hidden />
                        Anterior
                    </button>

                    {items.map((item, index) =>
                        item === 'ellipsis' ? (
                            <span key={`ellipsis-${index}`} className="px-1 text-text-muted" aria-hidden>
                                …
                            </span>
                        ) : (
                            <button
                                key={item}
                                type="button"
                                onClick={() => onPageChange(item)}
                                aria-current={item === page ? 'page' : undefined}
                                aria-label={`Página ${item}`}
                                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                                    item === page
                                        ? 'bg-primary-red text-white'
                                        : 'bg-white/10 hover:bg-white/20'
                                }`}
                            >
                                {item}
                            </button>
                        )
                    )}

                    <button
                        type="button"
                        onClick={() => onPageChange(page + 1)}
                        disabled={page >= pageCount}
                        className={`inline-flex items-center gap-1 ${pageButtonClass}`}
                    >
                        Siguiente
                        <ChevronRight className="w-4 h-4" aria-hidden />
                    </button>
                </nav>
            </div>
        </div>
    );
}