import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { getApiErrorMessage, getApiErrorRequestId, isOfflineError } from '@/infrastructure/api/errors';
import type { AlertaStock } from '@/domain/entities/Inventario';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import {
    Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow,
} from '@/presentation/components/ui/Table';

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

export function AdminInventoryAlertsPage() {
    const [alertas, setAlertas] = useState<AlertaStock[]>([]);
    const [umbralGeneral, setUmbralGeneral] = useState<number | null>(null);
    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);

    const load = useCallback(async () => {
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            const response = await inventarioService.listAlertas();
            setAlertas(response.alertas);
            setUmbralGeneral(response.umbralGeneral);
            setStatus('success');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudieron cargar las alertas de stock.'));
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, []);

    useEffect(() => {
        // eslint-disable-next-line react/set-state-in-effect
        void load();
    }, [load]);

    const handleRetry = () => void load();

    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="p-10 animate-fade-in">
            <div className="mb-6">
                <h2 className="text-3xl font-bold mb-2 tracking-tight">Alertas de stock</h2>
                <p className="text-text-muted text-lg">Repuestos con stock bajo su umbral efectivo</p>
                {status === 'success' && (
                    <p className="text-sm text-text-muted mt-2" aria-live="polite">
                        {alertas.length} alertas · umbral general: {umbralGeneral ?? 'sin configurar'}
                    </p>
                )}
            </div>

            {isOffline && <OfflineBanner message={error} onRetry={handleRetry} requestId={requestId} className="mb-6" />}
            {isServerError && alertas.length > 0 && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={handleRetry} />}>
                    {error} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'loading' ? (
                <div className="card p-16 flex justify-center"><LoadingState message="Cargando alertas..." /></div>
            ) : isServerError && alertas.length === 0 ? (
                <div className="card p-8">
                    <ErrorState title="No se pudieron cargar las alertas" message={error} requestId={requestId} onRetry={handleRetry} />
                </div>
            ) : alertas.length === 0 ? (
                <div className="card p-8">
                    <EmptyState icon={AlertTriangle} title="No hay alertas de stock" description="Todos los repuestos están sobre su umbral." />
                </div>
            ) : (
                <div className="card overflow-hidden">
                    <Table>
                        <TableHead className="border-b border-border-custom">
                            <TableRow>
                                <TableHeaderCell>Repuesto</TableHeaderCell>
                                <TableHeaderCell>Proveedor</TableHeaderCell>
                                <TableHeaderCell className="text-right">Stock</TableHeaderCell>
                                <TableHeaderCell className="text-right">Umbral</TableHeaderCell>
                                <TableHeaderCell className="text-right">Faltan</TableHeaderCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {alertas.map((a) => (
                                <TableRow key={a.repuestoId}>
                                    <TableCell className="font-medium">{a.nombre}</TableCell>
                                    <TableCell className="text-text-muted">{a.proveedorNombre}</TableCell>
                                    <TableCell className="text-right">{a.stock}</TableCell>
                                    <TableCell className="text-right">{a.umbralEfectivo}</TableCell>
                                    <TableCell className="text-right font-semibold text-status-red">{a.faltan}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
        </div>
    );
}