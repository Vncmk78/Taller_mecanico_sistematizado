import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, Truck, X } from 'lucide-react';
import { proveedorService } from '@/infrastructure/api/ProveedorService';
import { ProveedorFormDialog } from '@/presentation/components/inventory/ProveedorFormDialog';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { getApiErrorMessage, getApiErrorRequestId, isOfflineError } from '@/infrastructure/api/errors';
import type { Proveedor, TipoDistribuidor } from '@/domain/entities/Proveedor';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { isAdminInventoryMode, type InventoryPortalMode } from '@/presentation/utils/inventoryPortal';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeaderCell,
    TableRow,
} from '@/presentation/components/ui/Table';

/**\n * Tope de una sola página de `GET /proveedores`: el backend rechaza con 422\n * cualquier `limite` mayor a 200 (`LIMITE_MAXIMO` de MS3).\n */
export const LIMITE_PROVEEDORES = 200;

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

const TIPO_LABEL: Record<TipoDistribuidor, string> = {
    oficial: 'Oficial',
    generico: 'Genérico',
};

const TIPO_CLASS: Record<TipoDistribuidor, string> = {
    oficial: 'bg-status-blue/10 text-status-blue border border-status-blue/40',
    generico: 'bg-bg-secondary text-text-muted border border-border-custom',
};

function textoBuscable(proveedor: Proveedor): string {
    return [proveedor.nombre, proveedor.contacto].join(' ').toLowerCase();
}

interface AdminDistributorsPageProps {
    /** El portal mecánico consulta distribuidores sin poder editarlos. */
    mode?: InventoryPortalMode;
}

export function AdminDistributorsPage({ mode = 'admin' }: AdminDistributorsPageProps) {
    const isAdmin = isAdminInventoryMode(mode);
    const [proveedores, setProveedores] = useState<Proveedor[]>([]);
    const [total, setTotal] = useState(0);
    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [formOpen, setFormOpen] = useState(false);
    const [editing, setEditing] = useState<Proveedor | null>(null);
    const [formError, setFormError] = useState<string | null>(null);
    const [formSubmitting, setFormSubmitting] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Proveedor | null>(null);
    const [deleteSubmitting, setDeleteSubmitting] = useState(false);

    const loadProveedores = useCallback(async () => {
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            const response = await proveedorService.getProveedores({
                limite: LIMITE_PROVEEDORES,
            });
            setProveedores(response.proveedores);
            setTotal(response.total);
            setStatus('success');
        } catch (err) {
            setError(
                getApiErrorMessage(err, 'No se pudieron cargar los distribuidores del taller.')
            );
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, []);

    useEffect(() => {
        // La carga inicial es async: los setState ocurren después del await.
        // eslint-disable-next-line react/set-state-in-effect
        void loadProveedores();
    }, [loadProveedores]);

    const handleRetry = () => {
        void loadProveedores();
    };

    const handleCreate = async (values: { nombre: string; contacto: string; tipoDistribuidor: TipoDistribuidor }) => {
        setFormSubmitting(true);
        setFormError(null);
        try {
            await proveedorService.createProveedor(values);
            setFormOpen(false);
            setEditing(null);
            await loadProveedores();
        } catch (err) {
            setFormError(getApiErrorMessage(err, 'No se pudo crear el proveedor.'));
        } finally {
            setFormSubmitting(false);
        }
    };

    const handleUpdate = async (values: { nombre: string; contacto: string; tipoDistribuidor: TipoDistribuidor }) => {
        if (!editing) return;
        setFormSubmitting(true);
        setFormError(null);
        try {
            await proveedorService.updateProveedor(editing.proveedorId, values);
            setFormOpen(false);
            setEditing(null);
            await loadProveedores();
        } catch (err) {
            setFormError(getApiErrorMessage(err, 'No se pudo actualizar el proveedor.'));
        } finally {
            setFormSubmitting(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setDeleteSubmitting(true);
        try {
            await proveedorService.deleteProveedor(deleteTarget.proveedorId);
            setDeleteTarget(null);
            await loadProveedores();
        } catch {
            setDeleteTarget(null);
        } finally {
            setDeleteSubmitting(false);
        }
    };

    const filteredProveedores = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (term === '') return proveedores;
        return proveedores.filter((proveedor) => textoBuscable(proveedor).includes(term));
    }, [proveedores, search]);

    const hasActiveFilters = search.trim() !== '';

    const clearFilters = () => setSearch('');

    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
            <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-2 tracking-tight">Distribuidores</h2>
                    <p className="text-text-muted text-lg">
                        Proveedores de repuestos y su tipo de distribución
                    </p>
                </div>
                {isAdmin && (
                    <Button onClick={() => { setEditing(null); setFormError(null); setFormOpen(true); }}>
                        Nuevo proveedor
                    </Button>
                )}
                {status === 'success' && (
                    <p className="text-sm text-text-muted" aria-live="polite">
                        {filteredProveedores.length} de {total} distribuidores
                    </p>
                )}
            </div>

            <div className="card p-6 mb-6">
                <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                    <div
                        role="search"
                        aria-label="Buscar y filtrar distribuidores"
                        className="relative flex-1 min-w-[240px]"
                    >
                        <Search
                            className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted"
                            aria-hidden
                        />
                        <input
                            type="search"
                            name="buscar-distribuidores"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Buscar por nombre o contacto..."
                            aria-label="Buscar distribuidores"
                            autoComplete="off"
                            className="w-full py-2.5 pl-11 pr-4 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
                        />
                    </div>
                    {hasActiveFilters && filteredProveedores.length > 0 && (
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

            {isServerError && filteredProveedores.length > 0 && (
                <Alert
                    tone="error"
                    className="mb-6"
                    action={<RetryButton tone="error" onClick={handleRetry} />}
                >
                    {error ?? 'No se pudieron cargar los distribuidores del taller.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'success' && total > proveedores.length && (
                <Alert tone="info" className="mb-6">
                    El catálogo tiene {total} distribuidores; esta vista muestra los primeros{' '}
                    {proveedores.length}.
                </Alert>
            )}

            {status === 'loading' ? (
                <div className="card p-16 flex justify-center">
                    <LoadingState message="Cargando distribuidores..." />
                </div>
            ) : isServerError && filteredProveedores.length === 0 ? (
                <div className="card p-8">
                    <ErrorState
                        title="No se pudieron cargar los distribuidores"
                        message={error}
                        requestId={requestId}
                        onRetry={handleRetry}
                    />
                </div>
            ) : filteredProveedores.length === 0 ? (
                <div className="card p-8">
                    <EmptyState
                        icon={Truck}
                        title={
                            hasActiveFilters
                                ? `No se encontraron distribuidores para "${search.trim()}".`
                                : 'No hay distribuidores registrados'
                        }
                        description={
                            hasActiveFilters
                                ? 'Pruebe con otro nombre o contacto.'
                                : 'Los proveedores de repuestos aparecerán aquí cuando se registren.'
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
                            Distribuidores registrados con su contacto, tipo y cantidad de repuestos.
                        </caption>
                        <TableHead className="border-b border-border-custom">
                            <TableRow>
                                <TableHeaderCell>Nombre</TableHeaderCell>
                                <TableHeaderCell>Contacto</TableHeaderCell>
                                <TableHeaderCell>Tipo</TableHeaderCell>
                                <TableHeaderCell className="text-right">Repuestos</TableHeaderCell>
                                {isAdmin && <TableHeaderCell className="text-center">Acciones</TableHeaderCell>}
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filteredProveedores.map((proveedor) => (
                                <TableRow key={proveedor.proveedorId}>
                                    <TableCell className="font-medium">
                                        {proveedor.nombre}
                                    </TableCell>
                                    <TableCell className="text-text-muted">
                                        {proveedor.contacto}
                                    </TableCell>
                                    <TableCell>
                                        <span
                                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${TIPO_CLASS[proveedor.tipoDistribuidor]}`}
                                        >
                                            {TIPO_LABEL[proveedor.tipoDistribuidor]}
                                        </span>
                                    </TableCell>
                                    <TableCell className="text-right font-medium">
                                        {proveedor.cantidadRepuestos}
                                    </TableCell>
                                    {isAdmin && (
                                        <TableCell className="text-center">
                                            <div className="flex justify-center gap-2">
                                                <Button variant="secondary" onClick={() => { setEditing(proveedor); setFormError(null); setFormOpen(true); }}>Editar</Button>
                                                <Button variant="danger" onClick={() => setDeleteTarget(proveedor)}>Eliminar</Button>
                                            </div>
                                        </TableCell>
                                    )}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}

            {isAdmin && (
                <>
                    <ProveedorFormDialog
                        open={formOpen}
                        initial={editing}
                        isSubmitting={formSubmitting}
                        error={formError}
                        onSubmit={editing ? handleUpdate : handleCreate}
                        onClose={() => { setFormOpen(false); setEditing(null); setFormError(null); }}
                    />
                    <ConfirmDialog
                        open={!!deleteTarget}
                        title="Eliminar proveedor"
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
