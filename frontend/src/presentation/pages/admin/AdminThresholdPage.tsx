import { useCallback, useEffect, useState } from 'react';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { getApiErrorMessage, getApiErrorRequestId, isOfflineError } from '@/infrastructure/api/errors';
import type { CambioUmbral, UmbralGeneral } from '@/domain/entities/Inventario';
import { Button } from '@/presentation/components/ui/Button';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { Input } from '@/presentation/components/ui/Input';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import {
    Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow,
} from '@/presentation/components/ui/Table';

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

export function AdminThresholdPage() {
    const [umbral, setUmbral] = useState<UmbralGeneral | null>(null);
    const [historial, setHistorial] = useState<CambioUmbral[]>([]);
    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [valor, setValor] = useState('');
    const [observacion, setObservacion] = useState('');
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setStatus('loading');
        setError(null);
        setIsOffline(false);
        setRequestId(null);
        try {
            const [u, h] = await Promise.all([
                inventarioService.getUmbralGeneral(),
                inventarioService.getHistorialUmbral(null, true, 50),
            ]);
            setUmbral(u);
            setHistorial(h);
            setValor(u.umbralGeneral != null ? String(u.umbralGeneral) : '');
            setStatus('success');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudo cargar el umbral general.'));
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

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        const numero = Number(valor);
        if (!Number.isInteger(numero) || numero < 0) {
            setSaveError('Ingrese un entero mayor o igual a 0.');
            return;
        }
        setSaving(true);
        setSaveError(null);
        try {
            const updated = await inventarioService.cambiarUmbralGeneral({
                umbralGeneral: numero,
                observacion: observacion || null,
            });
            setUmbral(updated);
            setObservacion('');
            await load();
        } catch (err) {
            setSaveError(getApiErrorMessage(err, 'No se pudo actualizar el umbral general.'));
        } finally {
            setSaving(false);
        }
    };

    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="p-10 animate-fade-in">
            <h2 className="text-3xl font-bold mb-2 tracking-tight">Umbral general de stock</h2>
            <p className="text-text-muted text-lg mb-6">Configuración vigente e historial de cambios</p>

            {isOffline && <OfflineBanner message={error} onRetry={handleRetry} requestId={requestId} className="mb-6" />}

            {status === 'loading' ? (
                <div className="card p-16 flex justify-center"><LoadingState message="Cargando umbral..." /></div>
            ) : isServerError && !umbral ? (
                <div className="card p-8">
                    <ErrorState title="No se pudo cargar el umbral" message={error} requestId={requestId} onRetry={handleRetry} />
                </div>
            ) : (
                <div className="space-y-6">
                    <div className="card p-6">
                        <p className="text-text-muted text-sm mb-1">Umbral general vigente</p>
                        <p className="text-2xl font-bold mb-4">{umbral?.umbralGeneral ?? 'Sin configurar'}</p>
                        <form onSubmit={handleSave} className="flex flex-wrap gap-4 items-end">
                            <Input
                                label="Nuevo umbral"
                                type="number"
                                value={valor}
                                onChange={(e) => setValor(e.target.value)}
                            />
                            <Input
                                label="Observación"
                                value={observacion}
                                onChange={(e) => setObservacion(e.target.value)}
                            />
                            <Button type="submit" disabled={saving}>
                                {saving ? 'Guardando...' : 'Guardar'}
                            </Button>
                        </form>
                        {saveError && <p className="text-status-red text-sm mt-3">{saveError}</p>}
                    </div>

                    <div className="card overflow-hidden">
                        <h3 className="text-lg font-semibold p-4 border-b border-border-custom">Historial de cambios</h3>
                        {historial.length === 0 ? (
                            <div className="p-8">
                                <EmptyState title="Sin historial" description="Los cambios de umbral aparecerán aquí." />
                            </div>
                        ) : (
                            <Table>
                                <TableHead className="border-b border-border-custom">
                                    <TableRow>
                                        <TableHeaderCell>Fecha</TableHeaderCell>
                                        <TableHeaderCell className="text-right">Anterior</TableHeaderCell>
                                        <TableHeaderCell className="text-right">Nuevo</TableHeaderCell>
                                        <TableHeaderCell>Observación</TableHeaderCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {historial.map((h) => (
                                        <TableRow key={h.historialId}>
                                            <TableCell className="text-text-muted">{new Date(h.fechaHora).toLocaleString('es-CL')}</TableCell>
                                            <TableCell className="text-right">{h.valorAnterior ?? '-'}</TableCell>
                                            <TableCell className="text-right">{h.valorNuevo ?? '-'}</TableCell>
                                            <TableCell className="text-text-muted">{h.observacion ?? '-'}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}