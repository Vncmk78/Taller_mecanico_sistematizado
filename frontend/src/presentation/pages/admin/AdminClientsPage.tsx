import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, Users, X } from 'lucide-react';
import { authService } from '@/infrastructure/api/AuthService';
import { getApiErrorMessage, getApiErrorRequestId, isOfflineError } from '@/infrastructure/api/errors';
import type { UsuarioListado } from '@/domain/entities/User';
import { useDebouncedValue } from '@/presentation/hooks/useDebouncedValue';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
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

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

function textoBuscable(usuario: UsuarioListado): string {
    return [usuario.full_name, usuario.email].join(' ').toLowerCase();
}

/**
 * Listado de clientes del taller.
 *
 * MS1 no expone un endpoint `/clientes`: la fuente es `GET /auth/usuarios`
 * (solo administrador) y aquí se conservan las cuentas con rol `cliente`.
 */
export function AdminClientsPage() {
    const [clientes, setClientes] = useState<UsuarioListado[]>([]);
    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const debouncedSearch = useDebouncedValue(search);

    const loadClientes = useCallback(async () => {
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            const usuarios = await authService.listarUsuarios();
            setClientes(usuarios.filter((usuario) => usuario.roles.includes('cliente')));
            setStatus('success');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudieron cargar los clientes del taller.'));
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, []);

    useEffect(() => {
        // La carga inicial es async: los setState ocurren después del await.
        // eslint-disable-next-line react/set-state-in-effect
        void loadClientes();
    }, [loadClientes]);

    const handleRetry = () => {
        void loadClientes();
    };

    const filteredClientes = useMemo(() => {
        const term = debouncedSearch.trim().toLowerCase();
        if (term === '') return clientes;
        return clientes.filter((cliente) => textoBuscable(cliente).includes(term));
    }, [clientes, debouncedSearch]);

    const hasActiveFilters = search.trim() !== '';

    const clearFilters = () => setSearch('');

    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
            <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-2 tracking-tight">Clientes</h2>
                    <p className="text-text-muted text-lg">
                        Cuentas de clientes registradas en el taller
                    </p>
                </div>
                {status === 'success' && (
                    <p className="text-sm text-text-muted" aria-live="polite">
                        {filteredClientes.length} de {clientes.length} clientes
                    </p>
                )}
            </div>

            <div className="card p-6 mb-6">
                <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                    <div
                        role="search"
                        aria-label="Buscar y filtrar clientes"
                        className="relative flex-1 min-w-[240px]"
                    >
                        <Search
                            className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted"
                            aria-hidden
                        />
                        <input
                            type="search"
                            name="buscar-clientes"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Buscar por nombre o correo..."
                            aria-label="Buscar clientes"
                            autoComplete="off"
                            className="w-full py-2.5 pl-11 pr-4 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
                        />
                    </div>
                    {hasActiveFilters && filteredClientes.length > 0 && (
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

            {isServerError && filteredClientes.length > 0 && (
                <Alert
                    tone="error"
                    className="mb-6"
                    action={<RetryButton tone="error" onClick={handleRetry} />}
                >
                    {error ?? 'No se pudieron cargar los clientes del taller.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'loading' ? (
                <div className="card p-16 flex justify-center">
                    <LoadingState message="Cargando clientes..." />
                </div>
            ) : isServerError && filteredClientes.length === 0 ? (
                <div className="card p-8">
                    <ErrorState
                        title="No se pudieron cargar los clientes"
                        message={error}
                        requestId={requestId}
                        onRetry={handleRetry}
                    />
                </div>
            ) : filteredClientes.length === 0 ? (
                <div className="card p-8">
                    <EmptyState
                        icon={Users}
                        title={
                            hasActiveFilters
                                ? `No se encontraron clientes para "${search.trim()}".`
                                : 'No hay clientes registrados'
                        }
                        description={
                            hasActiveFilters
                                ? 'Pruebe con otro nombre o correo electrónico.'
                                : 'Las cuentas de clientes aparecerán aquí cuando se registren.'
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
                            Clientes registrados con su correo electrónico y estado de la cuenta.
                        </caption>
                        <TableHead className="border-b border-border-custom">
                            <TableRow>
                                <TableHeaderCell>Nombre</TableHeaderCell>
                                <TableHeaderCell>Correo electrónico</TableHeaderCell>
                                <TableHeaderCell className="text-center">Estado</TableHeaderCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filteredClientes.map((cliente) => (
                                <TableRow key={cliente.id}>
                                    <TableCell className="font-medium">
                                        {cliente.full_name}
                                    </TableCell>
                                    <TableCell className="text-text-muted">
                                        {cliente.email}
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <span
                                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                                                cliente.is_active
                                                    ? 'bg-status-green/10 text-status-green border-status-green/40'
                                                    : 'bg-status-red/10 text-status-red border-status-red/40'
                                            }`}
                                        >
                                            {cliente.is_active ? 'Activo' : 'Inactivo'}
                                        </span>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
        </div>
    );
}
