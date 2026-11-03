import { useCallback, useEffect, useMemo, useState } from 'react';
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

/** Texto buscable de un repuesto: código interno, nombre y proveedor. */
function textoBuscable(repuesto: Repuesto): string {
    return [repuesto.repuestoId, repuesto.nombre, repuesto.proveedorNombre]
        .join(' ')
        .toLowerCase();
}

export function AdminInventoryPage() {
    const [repuestos, setRepuestos] = useState<Repuesto[]>([]);
    const [total, setTotal] = useState(0);

    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [estado, setEstado] = useState<StockFilter>('todos');
    const [proveedores, setProveedores] = useState<Proveedor[]>([]);
    const [formOpen, setFormOpen] = useState(false);
    const [editing, setEditing] = useState<Repuesto | null>(null);
    const [formError, setFormError] = useState<string | null>(null);
    const [formSubmitting, setFormSubmitting] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Repuesto | null>(null);
    const [deleteSubmitting, setDeleteSubmitting] = useState(false);

    const loadRepuestos = useCallback(async () => {
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            const response = await repuestoService.getRepuestos({ limite: LIMITE_REPUESTOS });
            setRepuestos(response.repuestos);
            setTotal(response.total);

            setStatus('success');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudieron cargar los repuestos del inventario.'));
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, []);

    useEffect(() => {
        // La carga inicial es una llamada async: los setState ocurren después
        // del await, cuando la petición ya terminó.
        // eslint-disable-next-line react/set-state-in-effect
        void loadRepuestos();
    }, [loadRepuestos]);

    useEffect(() => {
        void (async () => {
            try {
                const response = await proveedorService.getProveedores({ limite: 200 });
                setProveedores(response.proveedores);
            } catch {
                setProveedores([]);
            }
        })();
    }, []);

    const handleRetry = () => {
        void loadRepuestos();
    };

    const handleCreate = async (values: { proveedorId: number; nombre: string; stockInicial?: number; umbralParticular: number | null }) => {
        setFormSubmitting(true);
        setFormError(null);
        try {
            await repuestoService.createRepuesto(values);
            setFormOpen(false);
            setEditing(null);
            await loadRepuestos();
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
            await loadRepuestos();
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
            await loadRepuestos();
        } catch {
            setDeleteTarget(null);
        } finally {
            setDeleteSubmitting(false);
        }
    };

    const filteredRepuestos = useMemo(() => {
        const term = search.trim().toLowerCase();
        return repuestos.filter((repuesto) => {
            if (term !== '' && !textoBuscable(repuesto).includes(term)) return false;
            if (estado === 'todos') return true;
            return getStockStatus(repuesto).key === estado;
        });
    }, [repuestos, search, estado]);

    const hasActiveFilters = search.trim() !== '' || estado !== 'todos';

    const clearFilters = () => {
        setSearch('');
        setEstado('todos');
    };

    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="p-10 animate-fade-in">
            <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-2 tracking-tight">Inventario</h2>
                    <p className="text-text-muted text-lg">Control de repuestos y stock del taller</p>
                </div>
                <Button onClick={() => { setEditing(null); setFormError(null); setFormOpen(true); }}>
                    Nuevo repuesto
                </Button>
                {status === 'success' && (
                    <p className="text-sm text-text-muted" aria-live="polite">
                        {filteredRepuestos.length} de {total} repuestos
                    </p>
                )}
            </div>

            <div className="card p-6 mb-6">
                <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                    <InventoryToolbar
                        className="flex-1"
                        search={search}
                        onSearchChange={setSearch}
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

            {isOffline && (
                <OfflineBanner
                    message={error}
                    onRetry={handleRetry}
                    requestId={requestId}
                    className="mb-6"
                />
            )}

            {isServerError && filteredRepuestos.length > 0 && (
                <Alert
                    tone="error"
                    className="mb-6"
                    action={<RetryButton tone="error" onClick={handleRetry} />}
                >
                    {error ?? 'No se pudieron cargar los repuestos del inventario.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'success' && total > repuestos.length && (
                <Alert tone="info" className="mb-6">
                    El catálogo tiene {total} repuestos; esta vista muestra los primeros{' '}
                    {repuestos.length}.
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
                <div className="card overflow-hidden">
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
                                        <div className="flex justify-center gap-2">
                                            <Button variant="secondary" onClick={() => { setEditing(repuesto); setFormError(null); setFormOpen(true); }}>Editar</Button>
                                            <Button variant="danger" onClick={() => setDeleteTarget(repuesto)}>Eliminar</Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}

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
        </div>
    );
}
