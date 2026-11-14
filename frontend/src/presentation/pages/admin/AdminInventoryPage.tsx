import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Package, X } from 'lucide-react';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { proveedorService } from '@/infrastructure/api/ProveedorService';
import { RepuestoFormDialog } from '@/presentation/components/inventory/RepuestoFormDialog';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { getApiErrorMessage, getApiErrorRequestId, isOfflineError } from '@/infrastructure/api/errors';
import type { Repuesto } from '@/domain/entities/Repuesto';
import type { Proveedor } from '@/domain/entities/Proveedor';
import { InventoryToolbar } from '@/presentation/components/inventory/InventoryToolbar';
import { StockStatusBadge } from '@/presentation/components/inventory/StockStatusBadge';
import { getStockStatus, type StockFilter } from '@/presentation/utils/stockStatus';
import { isAdminInventoryMode, type InventoryPortalMode } from '@/presentation/utils/inventoryPortal';
import { useDebouncedValue } from '@/presentation/hooks/useDebouncedValue';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';

import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeaderCell,
    TableRow,
} from '@/presentation/components/ui/Table';

/**
 * Tope de una sola página de `GET /repuestos`: el backend rechaza con 422
 * cualquier `limite` mayor a 200 (`LIMITE_MAXIMO` de MS3).
 */
export const LIMITE_REPUESTOS = 200;

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * Texto que el servidor NO filtra en `GET /repuestos?q`: el `q` de MS3 busca
 * solo por nombre. El proveedor y el código se comparan localmente sobre el
 * catálogo cargado para no perder esas búsquedas.
 */
function textoLocal(repuesto: Repuesto): string {
    return [repuesto.repuestoId, repuesto.proveedorNombre].join(' ').toLowerCase();
}

interface AdminInventoryPageProps {
    /** El portal mecánico comparte la vista, pero sin acciones de administración. */
    mode?: InventoryPortalMode;
}

export function AdminInventoryPage({ mode = 'admin' }: AdminInventoryPageProps) {
    const isAdmin = isAdminInventoryMode(mode);
    const stockDetailBase = isAdmin ? '/admin/inventario/stock' : '/mechanic/inventario/stock';
    // Catálogo completo cargado sin filtro (hasta LIMITE_REPUESTOS).
    const [repuestos, setRepuestos] = useState<Repuesto[]>([]);
    const [total, setTotal] = useState(0);
    // Coincidencias por nombre que devuelve el servidor para el término actual.
    const [resultadosBusqueda, setResultadosBusqueda] = useState<Repuesto[]>([]);
    const [totalBusqueda, setTotalBusqueda] = useState(0);
    const [isSearching, setIsSearching] = useState(false);

    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [searchError, setSearchError] = useState<string | null>(null);
    const [searchIsOffline, setSearchIsOffline] = useState(false);
    const [searchRequestId, setSearchRequestId] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [estado, setEstado] = useState<StockFilter>('todos');
    const [proveedores, setProveedores] = useState<Proveedor[]>([]);
    const [formOpen, setFormOpen] = useState(false);
    const [editing, setEditing] = useState<Repuesto | null>(null);
    const [formError, setFormError] = useState<string | null>(null);
    const [formSubmitting, setFormSubmitting] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Repuesto | null>(null);
    const [deleteSubmitting, setDeleteSubmitting] = useState(false);

    const debouncedSearch = useDebouncedValue(search);

    // Descarta respuestas fuera de orden al escribir rápido.
    const catalogoSeq = useRef(0);
    const busquedaSeq = useRef(0);
    const isFirstSearch = useRef(true);

    const loadRepuestos = useCallback(async () => {
        const seq = ++catalogoSeq.current;
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            const response = await repuestoService.getRepuestos({ limite: LIMITE_REPUESTOS });
            if (seq !== catalogoSeq.current) return;
            setRepuestos(response.repuestos);
            setTotal(response.total);
            setStatus('success');
        } catch (err) {
            if (seq !== catalogoSeq.current) return;
            setError(getApiErrorMessage(err, 'No se pudieron cargar los repuestos del inventario.'));
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, []);

    const buscar = useCallback(async (term: string) => {
        const seq = ++busquedaSeq.current;
        setIsSearching(true);
        try {
            const response = await repuestoService.getRepuestos({
                limite: LIMITE_REPUESTOS,
                q: term,
            });
            if (seq !== busquedaSeq.current) return;
            setResultadosBusqueda(response.repuestos);
            setTotalBusqueda(response.total);
            setSearchError(null);
            setSearchIsOffline(false);
            setSearchRequestId(null);
        } catch (err) {
            if (seq !== busquedaSeq.current) return;
            setSearchError(
                getApiErrorMessage(err, 'No se pudo buscar en el catálogo de repuestos.')
            );
            setSearchIsOffline(isOfflineError(err));
            setSearchRequestId(getApiErrorRequestId(err));
        } finally {
            if (seq === busquedaSeq.current) setIsSearching(false);
        }
    }, []);

    useEffect(() => {
        // La carga inicial es una llamada async: los setState ocurren después
        // del await, cuando la petición ya terminó.
        // eslint-disable-next-line react/set-state-in-effect
        void loadRepuestos();
    }, [loadRepuestos]);

    useEffect(() => {
        // La primera ejecución la cubre la carga inicial sin `q`.
        if (isFirstSearch.current) {
            isFirstSearch.current = false;
            return;
        }
        const term = debouncedSearch.trim();
        if (term === '') return;
        // La consulta es async: setIsSearching ocurre antes del await y la
        // respuesta actualiza el estado después.
        // eslint-disable-next-line react/set-state-in-effect
        void buscar(term);
    }, [debouncedSearch, buscar]);

    useEffect(() => {
        // Solo el formulario de alta/edición necesita el catálogo de proveedores.
        if (!isAdmin) return;
        void (async () => {
            try {
                const response = await proveedorService.getProveedores({ limite: 200 });
                setProveedores(response.proveedores);
            } catch {
                setProveedores([]);
            }
        })();
    }, [isAdmin]);

    const recargar = async () => {
        await loadRepuestos();
        const term = debouncedSearch.trim();
        if (term !== '') await buscar(term);
    };

    const handleRetry = () => {
        const term = debouncedSearch.trim();
        if (term !== '') {
            void buscar(term);
        } else {
            void loadRepuestos();
        }
    };

    const handleCreate = async (values: { proveedorId: number; nombre: string; stockInicial?: number; umbralParticular: number | null }) => {
        setFormSubmitting(true);
        setFormError(null);
        try {
            await repuestoService.createRepuesto(values);
            setFormOpen(false);
            setEditing(null);
            await recargar();
        } catch (err) {
            setFormError(getApiErrorMessage(err, 'No se pudo crear el repuesto.'));
        } finally {
            setFormSubmitting(false);
        }
    };

    const handleUpdate = async (values: { proveedorId: number; nombre: string; stockInicial?: number; umbralParticular: number | null }) => {
        if (!editing) return;
        setFormSubmitting(true);
        setFormError(null);
        try {
            await repuestoService.updateRepuesto(editing.repuestoId, {
                nombre: values.nombre,
                proveedorId: values.proveedorId,
                umbralParticular: values.umbralParticular,
            });
            setFormOpen(false);
            setEditing(null);
            await recargar();
        } catch (err) {
            setFormError(getApiErrorMessage(err, 'No se pudo actualizar el repuesto.'));
        } finally {
            setFormSubmitting(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setDeleteSubmitting(true);
        try {
            await repuestoService.deleteRepuesto(deleteTarget.repuestoId);
            setDeleteTarget(null);
            await recargar();
        } catch {
            setDeleteTarget(null);
        } finally {
            setDeleteSubmitting(false);
        }
    };

    const term = debouncedSearch.trim().toLowerCase();

    /**
     * Unión deduplicada: coincidencias por nombre del servidor (alcanzan todo
     * el catálogo) + coincidencias locales por proveedor/código (solo los
     * primeros LIMITE_REPUESTOS cargados).
     */
    const baseRepuestos = useMemo(() => {
        if (term === '') return repuestos;
        const locales = repuestos.filter((repuesto) => textoLocal(repuesto).includes(term));
        const vistos = new Set<number>();
        const union: Repuesto[] = [];
        for (const repuesto of [...resultadosBusqueda, ...locales]) {
            if (vistos.has(repuesto.repuestoId)) continue;
            vistos.add(repuesto.repuestoId);
            union.push(repuesto);
        }
        return union;
    }, [repuestos, resultadosBusqueda, term]);

    const filteredRepuestos = useMemo(
        () =>
            baseRepuestos.filter(
                (repuesto) => estado === 'todos' || getStockStatus(repuesto).key === estado
            ),
        [baseRepuestos, estado]
    );

    const hasActiveFilters = search.trim() !== '' || estado !== 'todos';

    const limpiarBusqueda = () => {
        setSearch('');
        setResultadosBusqueda([]);
        setTotalBusqueda(0);
        setSearchError(null);
        setSearchIsOffline(false);
        setSearchRequestId(null);
        setIsSearching(false);
    };

    const handleSearchChange = (value: string) => {
        if (value.trim() === '') {
            limpiarBusqueda();
            return;
        }
        setSearch(value);
    };

    const clearFilters = () => {
        limpiarBusqueda();
        setEstado('todos');
    };

    const isServerError = status === 'error' && !isOffline;
    const isSearchServerError = searchError !== null && !searchIsOffline;
    const errorMessage = error ?? searchError;
    const errorRequestId = requestId ?? searchRequestId;
    const showOffline = isOffline || searchIsOffline;

    return (
        <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
            <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-2 tracking-tight">Inventario</h2>
                    <p className="text-text-muted text-lg">
                        {isAdmin
                            ? 'Control de repuestos y stock del taller'
                            : 'Consulta de repuestos y disponibilidad del taller'}
                    </p>
                </div>
                {isAdmin && (
                    <Button onClick={() => { setEditing(null); setFormError(null); setFormOpen(true); }}>
                        Nuevo repuesto
                    </Button>
                )}
                {status !== 'loading' && (repuestos.length > 0 || term !== '') && (
                    <p className="text-sm text-text-muted" aria-live="polite">
                        {term !== ''
                            ? `${filteredRepuestos.length} de ${baseRepuestos.length} resultados`
                            : `${filteredRepuestos.length} de ${total} repuestos`}
                    </p>
                )}
            </div>

            <div className="card p-6 mb-6">
                <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                    <InventoryToolbar
                        className="flex-1"
                        search={search}
                        onSearchChange={handleSearchChange}
                        estado={estado}
                        onEstadoChange={setEstado}
                    />
                    {hasActiveFilters && filteredRepuestos.length > 0 && (
                        <Button variant="secondary" onClick={clearFilters} className="gap-2">
                            <X className="w-4 h-4" aria-hidden />
                            Limpiar filtros
                        </Button>
                    )}
                </div>
            </div>

            {showOffline && (
                <OfflineBanner
                    message={errorMessage}
                    onRetry={handleRetry}
                    requestId={errorRequestId}
                    className="mb-6"
                />
            )}

            {(isServerError || isSearchServerError) && filteredRepuestos.length > 0 && (
                <Alert
                    tone="error"
                    className="mb-6"
                    action={<RetryButton tone="error" onClick={handleRetry} />}
                >
                    {errorMessage ?? 'No se pudieron cargar los repuestos del inventario.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'success' && term === '' && total > repuestos.length && (
                <Alert tone="info" className="mb-6">
                    El catálogo tiene {total} repuestos; esta vista muestra los primeros{' '}
                    {repuestos.length}.
                </Alert>
            )}

            {term !== '' && totalBusqueda > resultadosBusqueda.length && (
                <Alert tone="info" className="mb-6">
                    La búsqueda por nombre encontró {totalBusqueda} repuestos; se muestran los
                    primeros {resultadosBusqueda.length}.
                </Alert>
            )}

            {status === 'loading' ? (
                <div className="card p-16 text-center">
                    <p className="text-text-muted">Cargando inventario...</p>
                </div>
            ) : isServerError && filteredRepuestos.length === 0 ? (
                <div className="card p-8">
                    <ErrorState
                        title="No se pudieron cargar los repuestos del inventario"
                        message={error}
                        requestId={requestId}
                        onRetry={handleRetry}
                    />
                </div>
            ) : isSearching && filteredRepuestos.length === 0 ? (
                <div className="card p-16 text-center">
                    <p className="text-text-muted">Buscando repuestos...</p>
                </div>
            ) : filteredRepuestos.length === 0 ? (
                <div className="card p-8">
                    <EmptyState
                        icon={Package}
                        title={
                            hasActiveFilters
                                ? 'No se encontraron repuestos con los filtros aplicados'
                                : 'No hay repuestos registrados'
                        }
                        description={
                            hasActiveFilters
                                ? 'Prueba con otro término de búsqueda o cambia el filtro de estado.'
                                : 'Los repuestos aparecerán aquí cuando se registren en el sistema.'
                        }
                        action={
                            hasActiveFilters ? (
                                <Button variant="secondary" onClick={clearFilters}>
                                    Limpiar filtros
                                </Button>
                            ) : undefined
                        }
                    />
                </div>
            ) : (
                <div className="card overflow-hidden" aria-busy={isSearching}>
                    <Table>
                        <caption className="sr-only">
                            Repuestos del inventario con su stock actual, umbral y estado.
                        </caption>
                        <TableHead className="border-b border-border-custom">
                            <TableRow>
                                <TableHeaderCell>Código</TableHeaderCell>
                                <TableHeaderCell>Repuesto</TableHeaderCell>
                                <TableHeaderCell>Proveedor</TableHeaderCell>
                                <TableHeaderCell className="text-right">Stock actual</TableHeaderCell>
                                <TableHeaderCell className="text-right">Umbral</TableHeaderCell>
                                <TableHeaderCell className="text-center">Estado de stock</TableHeaderCell>
                                <TableHeaderCell className="text-center">Acciones</TableHeaderCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filteredRepuestos.map((repuesto) => (
                                <TableRow key={repuesto.repuestoId}>
                                    <TableCell className="text-text-muted">
                                        #{repuesto.repuestoId}
                                    </TableCell>
                                    <TableCell className="font-medium">{repuesto.nombre}</TableCell>
                                    <TableCell className="text-text-muted">
                                        {repuesto.proveedorNombre}
                                    </TableCell>
                                    <TableCell className="text-right font-medium">
                                        {repuesto.stock}
                                    </TableCell>
                                    <TableCell className="text-right text-text-muted">
                                        {repuesto.umbralEfectivo ?? repuesto.umbralParticular ?? '-'}
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <StockStatusBadge repuesto={repuesto} />
                                    </TableCell>
                                    <TableCell className="text-center">
                                        {isAdmin ? (
                                            <div className="flex justify-center gap-2">
                                                <Button variant="secondary" onClick={() => { setEditing(repuesto); setFormError(null); setFormOpen(true); }}>Editar</Button>
                                                <Button variant="danger" onClick={() => setDeleteTarget(repuesto)}>Eliminar</Button>
                                            </div>
                                        ) : (
                                            <Link
                                                to={`${stockDetailBase}/${repuesto.repuestoId}`}
                                                className="inline-flex items-center justify-center px-4 py-2 rounded-lg border border-border-custom bg-surface text-text-main text-sm font-medium no-underline hover:bg-bg-secondary"
                                            >
                                                Ver stock
                                            </Link>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}

            {isAdmin && (
                <>
                    <RepuestoFormDialog
                        open={formOpen}
                        initial={editing}
                        proveedores={proveedores}
                        isSubmitting={formSubmitting}
                        error={formError}
                        onSubmit={editing ? handleUpdate : handleCreate}
                        onClose={() => { setFormOpen(false); setEditing(null); setFormError(null); }}
                    />
                    <ConfirmDialog
                        open={!!deleteTarget}
                        title="Eliminar repuesto"
                        description={`¿Eliminar ${deleteTarget?.nombre ?? ''}?`}
                        isLoading={deleteSubmitting}
                        onConfirm={handleDelete}
                        onCancel={() => setDeleteTarget(null)}
                    />
                </>
            )}
        </div>
    );
}
