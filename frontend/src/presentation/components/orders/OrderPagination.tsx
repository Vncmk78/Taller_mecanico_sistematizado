import { Pagination } from '@/presentation/components/ui/Pagination';
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

/**
 * Paginación del listado de órdenes: conserva los textos y el tamaño de página
 * históricos (6/12/24) sobre el componente genérico `ui/Pagination`.
 */
export function OrderPagination(props: OrderPaginationProps) {
    return (
        <Pagination
            {...props}
            label="órdenes"
            ariaLabel="Paginación de órdenes"
            sizeLabel="Órdenes por página"
            pageSizes={ORDER_PAGE_SIZES}
        />
    );
}
