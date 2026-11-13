import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, ShieldCheck, UserCog, X } from 'lucide-react';
import type { UserRole, UsuarioListado } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import {
    getApiErrorMessage,
    getApiErrorRequestId,
    isOfflineError,
} from '@/infrastructure/api/errors';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeaderCell,
    TableRow,
} from '@/presentation/components/ui/Table';
import { useToast } from '@/presentation/components/ui/toastContext';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

const ROLES_DISPONIBLES: readonly UserRole[] = ['cliente', 'mecanico', 'administrador'];

const ETIQUETA_ROL: Record<UserRole, string> = {
    cliente: 'Cliente',
    mecanico: 'Mecánico',
    administrador: 'Administrador',
};

function textoBuscable(usuario: UsuarioListado): string {
    return [usuario.full_name, usuario.email].join(' ').toLowerCase();
}

function tieneRol(usuario: UsuarioListado, rol: UserRole): boolean {
    return usuario.roles.includes(rol);
}

/**
 * Gestión de usuarios y roles (solo Administrador).
 *
 * MS1 es la autoridad: `GET /auth/usuarios` lista las cuentas y los endpoints
 * `/auth/usuarios/{id}/roles` acumulan o retiran roles de forma idempotente.
 * La propia cuenta del administrador queda bloqueada para evitar que se quite
 * a sí mismo el acceso, y se advierte cuando una cuenta quedaría sin roles.
 */
export function AdminUsersPage() {
    const user = useAuthStore((s) => s.user);
    const { showToast } = useToast();

    const [usuarios, setUsuarios] = useState<UsuarioListado[]>([]);
    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [search, setSearch] = useState('');

    const [editando, setEditando] = useState<UsuarioListado | null>(null);
    const [rolesSeleccionados, setRolesSeleccionados] = useState<UserRole[]>([]);
    const [guardando, setGuardando] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);
    const [confirmarSinRoles, setConfirmarSinRoles] = useState(false);

    const cargar = useCallback(async () => {
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            setUsuarios(await authService.listarUsuarios());
            setStatus('success');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudieron cargar los usuarios.'));
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, []);

    useEffect(() => {
        // La carga inicial es async: los setState ocurren después del await.
        // eslint-disable-next-line react/set-state-in-effect
        void cargar();
    }, [cargar]);

    const filtrados = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (term === '') return usuarios;
        return usuarios.filter((usuario) => textoBuscable(usuario).includes(term));
    }, [usuarios, search]);

    const hasActiveFilters = search.trim() !== '';
    const isServerError = status === 'error' && !isOffline;

    const abrirEdicion = (usuario: UsuarioListado) => {
        if (usuario.id === user?.id) return;
        setEditando(usuario);
        setRolesSeleccionados([...usuario.roles]);
        setActionError(null);
        setConfirmarSinRoles(false);
    };

    const cerrarEdicion = () => {
        if (guardando) return;
        setEditando(null);
        setConfirmarSinRoles(false);
        setActionError(null);
    };

    const alternarRol = (rol: UserRole) => {
        setRolesSeleccionados((prev) =>
            prev.includes(rol) ? prev.filter((r) => r !== rol) : [...prev, rol]
        );
    };

    const guardarRoles = async () => {
        if (!editando || guardando) return;
        // Defensa adicional: el botón ya está deshabilitado en la propia cuenta.
        if (editando.id === user?.id) return;

        if (rolesSeleccionados.length === 0 && !confirmarSinRoles) {
            setConfirmarSinRoles(true);
            return;
        }

        const aAsignar = rolesSeleccionados.filter((rol) => !tieneRol(editando, rol));
        const aRetirar = editando.roles.filter((rol) => !rolesSeleccionados.includes(rol));

        setGuardando(true);
        setActionError(null);
        try {
            let actualizado = editando;
            for (const rol of aAsignar) {
                actualizado = await authService.asignarRol(editando.id, rol);
            }
            for (const rol of aRetirar) {
                actualizado = await authService.retirarRol(editando.id, rol);
            }
            setUsuarios((prev) =>
                prev.map((usuario) => (usuario.id === actualizado.id ? actualizado : usuario))
            );
            showToast(`Roles de ${actualizado.full_name} actualizados.`, 'success');
            setEditando(null);
            setConfirmarSinRoles(false);
        } catch (err) {
            setActionError(getApiErrorMessage(err, 'No se pudieron actualizar los roles.'));
            // Si una llamada intermedia se aplicó, el listado recargado refleja
            // el estado real del servidor en vez de uno optimista.
            try {
                setUsuarios(await authService.listarUsuarios());
            } catch {
                // Se conserva el listado anterior con el mensaje de error.
            }
        } finally {
            setGuardando(false);
        }
    };

    return (
        <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
            <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
                <div>
                    <h1 className="text-3xl font-bold mb-2 tracking-tight flex items-center gap-3">
                        <UserCog className="w-7 h-7 text-text-muted" aria-hidden />
                        Usuarios y roles
                    </h1>
                    <p className="text-text-muted text-lg">
                        Asigne o retire roles de las cuentas del taller.
                    </p>
                </div>
                {status === 'success' && (
                    <p className="text-sm text-text-muted" aria-live="polite">
                        {filtrados.length} de {usuarios.length} usuarios
                    </p>
                )}
            </div>

            <div className="card p-6 mb-6">
                <div
                    role="search"
                    aria-label="Buscar usuarios"
                    className="relative max-w-md"
                >
                    <Search
                        className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted"
                        aria-hidden
                    />
                    <input
                        type="search"
                        name="buscar-usuarios"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Buscar por nombre o correo..."
                        aria-label="Buscar usuarios"
                        autoComplete="off"
                        className="w-full py-2.5 pl-11 pr-4 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
                    />
                </div>
            </div>

            {isOffline && (
                <OfflineBanner
                    message={error}
                    onRetry={() => void cargar()}
                    requestId={requestId}
                    className="mb-6"
                />
            )}

            {isServerError && filtrados.length > 0 && (
                <Alert
                    tone="error"
                    className="mb-6"
                    action={<RetryButton tone="error" onClick={() => void cargar()} />}
                >
                    {error ?? 'No se pudieron cargar los usuarios.'} Se muestran los últimos datos
                    disponibles.
                </Alert>
            )}

            {actionError && (
                <Alert tone="error" className="mb-6">
                    {actionError}
                </Alert>
            )}

            {editando && (
                <section
                    className="card p-6 mb-6 animate-fade-in"
                    aria-labelledby="editar-roles-title"
                >
                    <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
                        <div>
                            <h2 id="editar-roles-title" className="text-xl font-semibold">
                                Roles de {editando.full_name}
                            </h2>
                            <p className="text-sm text-text-muted">{editando.email}</p>
                        </div>
                        <button
                            type="button"
                            onClick={cerrarEdicion}
                            disabled={guardando}
                            aria-label="Cerrar edición de roles"
                            className="text-text-muted hover:text-text-main bg-transparent border-none cursor-pointer disabled:opacity-50"
                        >
                            <X className="w-5 h-5" aria-hidden />
                        </button>
                    </div>

                    <fieldset className="flex flex-col gap-3 mb-4">
                        <legend className="sr-only">Roles de la cuenta</legend>
                        {ROLES_DISPONIBLES.map((rol) => (
                            <label
                                key={rol}
                                className="flex items-center gap-3 text-sm text-text-main cursor-pointer"
                            >
                                <input
                                    type="checkbox"
                                    checked={rolesSeleccionados.includes(rol)}
                                    onChange={() => alternarRol(rol)}
                                    disabled={guardando}
                                    className="w-4 h-4 accent-primary-blue"
                                />
                                <span className="flex items-center gap-2">
                                    <ShieldCheck className="w-4 h-4 text-text-muted" aria-hidden />
                                    {ETIQUETA_ROL[rol]}
                                </span>
                            </label>
                        ))}
                    </fieldset>

                    {rolesSeleccionados.length === 0 && (
                        <Alert tone="warning" className="mb-4">
                            Sin roles, esta cuenta no podrá acceder a ningún portal del sistema.
                        </Alert>
                    )}

                    <div className="flex flex-wrap gap-3">
                        <Button onClick={() => void guardarRoles()} isLoading={guardando}>
                            Guardar roles
                        </Button>
                        <Button variant="secondary" onClick={cerrarEdicion} disabled={guardando}>
                            Cancelar
                        </Button>
                    </div>
                </section>
            )}

            {status === 'loading' ? (
                <div className="card p-16 flex justify-center">
                    <LoadingState message="Cargando usuarios..." />
                </div>
            ) : isServerError && filtrados.length === 0 ? (
                <div className="card p-8">
                    <ErrorState
                        title="No se pudieron cargar los usuarios"
                        message={error}
                        requestId={requestId}
                        onRetry={() => void cargar()}
                    />
                </div>
            ) : filtrados.length === 0 ? (
                <div className="card p-8">
                    <EmptyState
                        icon={UserCog}
                        title={
                            hasActiveFilters
                                ? `No se encontraron usuarios para "${search.trim()}".`
                                : 'No hay usuarios registrados'
                        }
                        description={
                            hasActiveFilters
                                ? 'Pruebe con otro nombre o correo electrónico.'
                                : 'Las cuentas aparecerán aquí cuando se registren.'
                        }
                        action={
                            hasActiveFilters ? (
                                <Button variant="secondary" onClick={() => setSearch('')}>
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
                            Usuarios con sus roles, estado de la cuenta y acción para editarlos.
                        </caption>
                        <TableHead className="border-b border-border-custom">
                            <TableRow>
                                <TableHeaderCell>Nombre</TableHeaderCell>
                                <TableHeaderCell>Correo electrónico</TableHeaderCell>
                                <TableHeaderCell>Roles</TableHeaderCell>
                                <TableHeaderCell className="text-center">Estado</TableHeaderCell>
                                <TableHeaderCell className="text-right">Acción</TableHeaderCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filtrados.map((usuario) => {
                                const esPropiaCuenta = usuario.id === user?.id;
                                return (
                                    <TableRow key={usuario.id}>
                                        <TableCell className="font-medium">
                                            <span className="flex items-center gap-2 flex-wrap">
                                                {usuario.full_name}
                                                {esPropiaCuenta && (
                                                    <span className="text-xs font-normal text-text-muted">
                                                        (su cuenta)
                                                    </span>
                                                )}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-text-muted">
                                            {usuario.email}
                                        </TableCell>
                                        <TableCell>
                                            {usuario.roles.length === 0 ? (
                                                <span className="text-status-red text-sm">
                                                    Sin roles
                                                </span>
                                            ) : (
                                                <span className="flex flex-wrap gap-2">
                                                    {usuario.roles.map((rol) => (
                                                        <span
                                                            key={rol}
                                                            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border bg-primary-blue/10 text-primary-blue border-primary-blue/30"
                                                        >
                                                            {ETIQUETA_ROL[rol]}
                                                        </span>
                                                    ))}
                                                </span>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-center">
                                            <span
                                                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                                                    usuario.is_active
                                                        ? 'bg-status-green/10 text-status-green border-status-green/40'
                                                        : 'bg-status-red/10 text-status-red border-status-red/40'
                                                }`}
                                            >
                                                {usuario.is_active ? 'Activo' : 'Inactivo'}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button
                                                variant="secondary"
                                                className="py-2 px-4 text-sm whitespace-nowrap"
                                                onClick={() => abrirEdicion(usuario)}
                                                disabled={esPropiaCuenta}
                                                title={
                                                    esPropiaCuenta
                                                        ? 'No puede modificar los roles de su propia cuenta.'
                                                        : undefined
                                                }
                                            >
                                                Editar roles
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </div>
            )}

            <ConfirmDialog
                open={confirmarSinRoles}
                tone="danger"
                title="¿Dejar la cuenta sin roles?"
                description={
                    editando
                        ? `${editando.full_name} no podrá acceder a ningún portal del sistema hasta que un administrador le asigne un rol.`
                        : ''
                }
                confirmLabel="Guardar sin roles"
                isLoading={guardando}
                onConfirm={() => void guardarRoles()}
                onCancel={() => setConfirmarSinRoles(false)}
            />
        </div>
    );
}
