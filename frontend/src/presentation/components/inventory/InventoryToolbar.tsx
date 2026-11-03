import { Search } from 'lucide-react';
import { STOCK_STATUS_OPTIONS, type StockFilter } from '@/presentation/utils/stockStatus';

interface InventoryToolbarProps {
    search: string;
    onSearchChange: (value: string) => void;
    estado: StockFilter;
    onEstadoChange: (value: StockFilter) => void;
    className?: string;
}

/**
 * Barra de controles del inventario: búsqueda por texto + filtro por estado de
 * stock. Mismo lenguaje visual y misma estructura accesible que
 * `OrderListToolbar` (región de búsqueda + controles etiquetados).
 */
export function InventoryToolbar({
    search,
    onSearchChange,
    estado,
    onEstadoChange,
    className = '',
}: InventoryToolbarProps) {
    return (
        <div
            role="search"
            aria-label="Buscar y filtrar repuestos"
            className={`flex flex-wrap items-center gap-4 ${className}`}
        >
            <div className="relative flex-1 min-w-[240px]">
                <Search
                    className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted"
                    aria-hidden
                />
                <input
                    type="search"
                    name="buscar-repuestos"
                    value={search}
                    onChange={(e) => onSearchChange(e.target.value)}
                    placeholder="Buscar por código, nombre o proveedor..."
                    aria-label="Buscar repuestos"
                    autoComplete="off"
                    className="w-full py-2.5 pl-11 pr-4 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
                />
            </div>

            <label className="flex items-center gap-2 text-sm text-text-muted">
                <span className="whitespace-nowrap">Estado</span>
                <select
                    value={estado}
                    onChange={(e) => onEstadoChange(e.target.value as StockFilter)}
                    aria-label="Filtrar por estado de stock"
                    className="bg-surface border border-border-custom rounded-lg px-3 py-2.5 text-text-main text-sm outline-none focus:border-primary-blue"
                >
                    <option value="todos">Todos los estados</option>
                    {STOCK_STATUS_OPTIONS.map(({ key, label }) => (
                        <option key={key} value={key}>
                            {label}
                        </option>
                    ))}
                </select>
            </label>
        </div>
    );
}
