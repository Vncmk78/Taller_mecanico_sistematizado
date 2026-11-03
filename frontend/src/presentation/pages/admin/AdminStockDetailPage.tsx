import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { getApiErrorMessage, getApiErrorRequestId, isOfflineError } from '@/infrastructure/api/errors';
import type { StockDetalle } from '@/domain/entities/Inventario';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import {
    Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow,
} from '@/presentation/components/ui/Table';

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

export function AdminStockDetailPage() {
    const { repuestoId } = useParams();
    const id = Number(repuestoId);
    const [stock, setStock] = useState<StockDetalle | null>(null);
    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);

    const load = useCallback(async () => {
        if (!Number.isFinite(id) || id <= 0) return;
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            const response = await inventarioService.getStock(id);
            setStock(response);
            setStatus('success');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudo cargar el stock del repuesto.'));
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, [id]);

    useEffect(() => {
        // eslint-disable-next-line react/set-state-in-effect
        void load();
    }, [load]);

    const handleRetry = () => void load();
    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="p-10 animate-fade-in">
            <h2 className="text-3xl font-bold mb-2 tracking-tight">Stock del repuesto #{id}</h2>
            <p className="text-text-muted text-lg mb-6">Stock físico, comprometido y disponible</p>

            {isOffline && <OfflineBanner message={error} onRetry={handleRetry} requestId={requestId} className="mb-6" />}
            {isServerError && !stock && (
                <div className="card p-8">
                    <ErrorState title="No se pudo cargar el stock" message={error} requestId={requestId} onRetry={handleRetry} />
                </div>
            )}

            {status === 'loading' ? (
                <div className="card p-16 flex justify-center"><LoadingState message="Cargando stock..." /></div>
            ) : stock ? (
                <div className="space-y-6">
                    <div className="card p-6 grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div><p className="text-text-muted text-sm">Repuesto</p><p className="font-semibold">{stock.nombre}</p></div>
                        <div><p className="text-text-muted text-sm">Proveedor</p><p className="font-semibold">{stock.proveedorNombre}</p></div>
                        <div><p className="text-text-muted text-sm">Stock físico</p><p className="font-semibold">{stock.stock}</p></div>
                        <div><p className="text-text-muted text-sm">Comprometido</p><p className="font-semibold">{stock.comprometido}</p></div>
                        <div><p className="text-text-muted text-sm">Disponible</p><p className="font-semibold">{stock.disponible}</p></div>
                        <div><p className="text-text-muted text-sm">Umbral efectivo</p><p className="font-semibold">{stock.umbralEfectivo ?? '-'}</p></div>
                        <div><p className="text-text-muted text-sm">Bajo umbral</p><p className="font-semibold">{stock.bajoUmbral ? 'Sí' : 'No'}</p></div>
                    </div>

                    {stock.compromisos.length > 0 && (
                        <div className="card overflow-hidden">
                            <Table>
                                <TableHead className="border-b border-border-custom">
                                    <TableRow>
                                        <TableHeaderCell>Orden</TableHeaderCell>
                                        <TableHeaderCell className="text-right">Comprometido</TableHeaderCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {stock.compromisos.map((c) => (
                                        <TableRow key={c.ordenId}>
                                            <TableCell>#{c.ordenId}</TableCell>
                                            <TableCell className="text-right">{c.comprometido}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </div>
            ) : (
                <div className="card p-8">
                    <EmptyState title="No se encontró el repuesto" description="Verifique el identificador." />
                </div>
            )}
        </div>
    );
}