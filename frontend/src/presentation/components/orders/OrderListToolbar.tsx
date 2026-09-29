import { Search } from 'lucide-react';
import { ESTADOS_ORDEN } from '@/domain/entities/Order';
import type { OrderEstadoFilter } from '@/presentation/hooks/useOrderListFilters';

interface OrderListToolbarProps {
    search: string;
    onSearchChange: (value: string) => void;
    estadoCodigo: OrderEstadoFilter;
    onEstadoChange: (value: OrderEstadoFilter) => void;
    searchPlaceholder?: string;
    className?: string;
}

/**
 * Barra de controles del listado de órdenes: búsqueda por texto + filtro por
 * estado (catálogo fijo de 8). Mismo lenguaje visual que los inputs existentes.
 */
export function OrderListToolbar({
    search,
    onSearchChange,
    estadoCodigo,
    onEstadoChange,
    searchPlaceholder = 'Buscar por n° de orden, patente o estado...',
    className = '',
}: OrderListToolbarProps) {
    const codigos = Object.keys(ESTADOS_ORDEN)
        .map(Number)
        .sort((a, b) => a - b);

    return (
        <div className={`flex flex-wrap items-center gap-4 ${className}`}>
            <div className="relative flex-1 min-w-[240px]">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" aria-hidden />
                <input
                    type="text"
                    value={search}
                    onChange={(e) => onSearchChange(e.target.value)}
                    placeholder={searchPlaceholder}
                    aria-label="Buscar órdenes"
                    className="w-full py-2.5 pl-11 pr-4 bg-black/40 border border-border-custom rounded-lg text-white text-sm outline-none focus:border-primary-red"
                />
            </div>

            <label className="flex items-center gap-2 text-sm text-text-muted">
                <span className="whitespace-nowrap">Estado</span>
                <select
                    value={estadoCodigo === 'all' ? 'all' : String(estadoCodigo)}
                    onChange={(e) => {
                        const value = e.target.value;
                        onEstadoChange(value === 'all' ? 'all' : Number(value));
                    }}
                    aria-label="Filtrar por estado"
                    className="bg-black/40 border border-border-custom rounded-lg px-3 py-2.5 text-white text-sm outline-none focus:border-primary-red"
                >
                    <option value="all">Todos los estados</option>
                    {codigos.map((codigo) => (
                        <option key={codigo} value={codigo}>
                            {ESTADOS_ORDEN[codigo]}
                        </option>
                    ))}
                </select>
            </label>
        </div>
    );
}