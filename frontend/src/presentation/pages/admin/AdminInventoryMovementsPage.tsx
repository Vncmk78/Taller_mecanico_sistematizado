import { useCallback, useEffect, useState } from 'react';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { getApiErrorMessage, getApiErrorRequestId, isOfflineError } from '@/infrastructure/api/errors';
import type { Movimiento, TipoMovimiento } from '@/domain/entities/Inventario';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { FormActions } from '@/presentation/components/ui/FormActions';
import { FormModal } from '@/presentation/components/ui/FormModal';
import { Input } from '@/presentation/components/ui/Input';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { Select } from '@/presentation/components/ui/Select';
import {
    Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow,
} from '@/presentation/components/ui/Table';

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

const TIPOS: TipoMovimiento[] = ['ingreso', 'ajuste', 'compromiso', 'consumo', 'liberacion'];

export function AdminInventoryMovementsPage() {
    const [movimientos, setMovimientos] = useState<Movimiento[]>([]);
    const [total, setTotal] = useState(0);
    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [repuestoId, setRepuestoId] = useState('');
    const [tipo, setTipo] = useState('');
    const [movementOpen, setMovementOpen] = useState(false);
    const [movementSubmitting, setMovementSubmitting] = useState(false);
    const [movementError, setMovementError] = useState<string | null>(null);
    const [mRepuestoId, setMRepuestoId] = useState('');
    const [mTipo, setMTipo] = useState<TipoMovimiento>('ingreso');
    const [mCantidad, setMCantidad] = useState('');
    const [mOrdenId, setMOrdenId] = useState('');
    const [mProveedorId, setMProveedorId] = useState('');

    const load = useCallback(async () => {
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            const response = await inventarioService.listMovimientos({
                repuestoId: repuestoId ? Number(repuestoId) : null,
                tipo: tipo ? (tipo as TipoMovimiento) : null,
                limite: 50,
            });
            setMovimientos(response.movimientos);
            setTotal(response.total);
            setStatus('success');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudieron cargar los movimientos.'));
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, [repuestoId, tipo]);

    useEffect(() => {
        // eslint-disable-next-line react/set-state-in-effect
        void load();
    }, [load]);

    const handleRetry = () => void load();

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        const repuestoIdNum = Number(mRepuestoId);
        const cantidadNum = Number(mCantidad);
        if (!Number.isFinite(repuestoIdNum) || repuestoIdNum <= 0) {
            setMovementError('Repuesto inválido.');
            return;
        }
        if (!Number.isFinite(cantidadNum) || cantidadNum === 0) {
            setMovementError('Cantidad inválida.');
            return;
        }
        setMovementSubmitting(true);
        setMovementError(null);
        try {
            await inventarioService.registrarMovimiento({
                claveOperacion: crypto.randomUUID(),
                repuestoId: repuestoIdNum,
                tipo: mTipo,
                cantidad: cantidadNum,
                ordenId: mOrdenId ? Number(mOrdenId) : null,
                proveedorId: mProveedorId ? Number(mProveedorId) : null,
            });
            setMovementOpen(false);
            setMRepuestoId('');
            setMCantidad('');
            setMOrdenId('');
            setMProveedorId('');
            await load();
        } catch (err) {
            setMovementError(getApiErrorMessage(err, 'No se pudo registrar el movimiento.'));
        } finally {
            setMovementSubmitting(false);
        }
    };
    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
            <div className="mb-6 flex justify-between items-center gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-2 tracking-tight">Movimientos de inventario</h2>
                    <p className="text-text-muted text-lg">Historial de ingresos, ajustes, compromisos, consumos y liberaciones</p>
                    {status === 'success' && <p className="text-sm text-text-muted mt-2" aria-live="polite">{total} movimientos</p>}
                </div>
                <button
                    type="button"
                    onClick={() => { setMovementError(null); setMovementOpen(true); }}
                    className="px-4 py-2 rounded-lg bg-primary-blue text-white text-sm font-medium"
                >
                    Registrar movimiento
                </button>
            </div>

            <div className="card p-6 mb-6 flex flex-wrap gap-4 items-end">
                <Input
                    label="Repuesto ID"
                    type="number"
                    value={repuestoId}
                    onChange={(e) => setRepuestoId(e.target.value)}
                    containerClassName="mb-0"
                />
                <Select
                    label="Tipo"
                    value={tipo}
                    onChange={(e) => setTipo(e.target.value)}
                    containerClassName="mb-0"
                >
                    <option value="">Todos</option>
                    {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
                </Select>
                <button
                    type="button"
                    onClick={handleRetry}
                    className="px-4 py-2 rounded-lg bg-primary-blue text-white text-sm font-medium"
                >
                    Buscar
                </button>
            </div>

            {isOffline && <OfflineBanner message={error} onRetry={handleRetry} requestId={requestId} className="mb-6" />}
            {isServerError && movimientos.length > 0 && (
                <div className="card p-6 mb-6 flex flex-wrap items-center justify-between gap-4">
                    <p className="text-status-red text-sm">{error}</p>
                    <RetryButton tone="error" onClick={handleRetry} />
                </div>
            )}

            {status === 'loading' ? (
                <div className="card p-16 flex justify-center"><LoadingState message="Cargando movimientos..." /></div>
            ) : isServerError && movimientos.length === 0 ? (
                <div className="card p-8">
                    <ErrorState title="No se pudieron cargar los movimientos" message={error} requestId={requestId} onRetry={handleRetry} />
                </div>
            ) : movimientos.length === 0 ? (
                <div className="card p-8">
                    <EmptyState title="No hay movimientos" description="Los movimientos de stock aparecerán aquí." />
                </div>
            ) : (
                <div className="card overflow-hidden">
                    <Table>
                        <TableHead className="border-b border-border-custom">
                            <TableRow>
                                <TableHeaderCell>Fecha</TableHeaderCell>
                                <TableHeaderCell>Repuesto</TableHeaderCell>
                                <TableHeaderCell>Tipo</TableHeaderCell>
                                <TableHeaderCell className="text-right">Cantidad</TableHeaderCell>
                                <TableHeaderCell>Orden</TableHeaderCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {movimientos.map((m) => (
                                <TableRow key={m.movimientoId}>
                                    <TableCell className="text-text-muted">{new Date(m.fechaHora).toLocaleString('es-CL')}</TableCell>
                                    <TableCell className="font-medium">#{m.repuestoId}</TableCell>
                                    <TableCell>{m.tipo}</TableCell>
                                    <TableCell className="text-right">{m.cantidad}</TableCell>
                                    <TableCell className="text-text-muted">{m.ordenId ?? '-'}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}

            {movementOpen && (
                <FormModal
                    open={movementOpen}
                    title="Registrar movimiento"
                    onClose={() => setMovementOpen(false)}
                >
                    <form onSubmit={handleRegister} className="space-y-4">
                        <Input
                            label="Repuesto ID"
                            type="number"
                            value={mRepuestoId}
                            onChange={(e) => setMRepuestoId(e.target.value)}
                            containerClassName="mb-0"
                        />
                        <Select
                            label="Tipo"
                            value={mTipo}
                            onChange={(e) => setMTipo(e.target.value as TipoMovimiento)}
                            containerClassName="mb-0"
                        >
                            {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
                        </Select>
                        <Input
                            label="Cantidad"
                            type="number"
                            value={mCantidad}
                            onChange={(e) => setMCantidad(e.target.value)}
                            containerClassName="mb-0"
                        />
                        <Input
                            label="Orden ID (opcional)"
                            type="number"
                            value={mOrdenId}
                            onChange={(e) => setMOrdenId(e.target.value)}
                            containerClassName="mb-0"
                        />
                        <Input
                            label="Proveedor ID (opcional)"
                            type="number"
                            value={mProveedorId}
                            onChange={(e) => setMProveedorId(e.target.value)}
                            containerClassName="mb-0"
                        />
                        {movementError && <p className="text-status-red text-sm">{movementError}</p>}
                        <FormActions>
                            <button type="button" onClick={() => setMovementOpen(false)} className="px-4 py-2 rounded-lg border border-border-custom text-sm">Cancelar</button>
                            <button type="submit" disabled={movementSubmitting} className="px-4 py-2 rounded-lg bg-primary-blue text-white text-sm font-medium">
                                {movementSubmitting ? 'Guardando...' : 'Registrar'}
                            </button>
                        </FormActions>
                    </form>
                </FormModal>
            )}
        </div>
    );
}