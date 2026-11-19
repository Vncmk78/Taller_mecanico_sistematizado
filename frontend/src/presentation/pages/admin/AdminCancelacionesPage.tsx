import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardX } from 'lucide-react';
import type { SolicitudCancelacion } from '@/domain/entities/SolicitudCancelacion';
import { ESTADOS_ORDEN } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import {
    getApiErrorMessage,
    getApiErrorRequestId,
    isOfflineError,
} from '@/infrastructure/api/errors';
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
import { formatDateTime } from '@/presentation/utils/orderDisplay';

type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * Bandeja de cancelaciones pendientes (solo Administrador). Lista únicamente
 * las órdenes con una solicitud registrada por el Cliente y permite
 * confirmarlas contra POST /ordenes/{id}/cancelacion/confirmacion.
 */
export function AdminCancelacionesPage() {
    const { showToast } = useToast();
    const [solicitudes, setSolicitudes] = useState<SolicitudCancelacion[]>([]);
    const [status, setStatus] = useState<FetchStatus>('loading');
    const [error, setError] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [seleccionada, setSeleccionada] = useState<SolicitudCancelacion | null>(null);
    const [confirmando, setConfirmando] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);

    const load = useCallback(async () => {
    setStatus('loading');
    setError(null);
    setIsOffline(false);
    setRequestId(null);
    try {
        const pendientes = await orderService.getCancelacionesPendientes();
        setSolicitudes(pendientes);
        setStatus('success');
    } catch (err) {
        setError(getApiErrorMessage(err, 'No se pudieron cargar las cancelaciones pendientes.'));
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

    const confirmar = async () => {
    if (!seleccionada || confirmando) return;
    setConfirmando(true);
    setActionError(null);
    try {
        const orden = await orderService.confirmarCancelacion(seleccionada.ordenId);
        setSolicitudes((prev) => prev.filter((s) => s.id !== seleccionada.id));
        setSeleccionada(null);
        showToast(`Orden n° ${orden.id} cancelada.`, 'success');
    } catch (err) {
        setActionError(getApiErrorMessage(err, 'No se pudo confirmar la cancelación.'));
        setSeleccionada(null);
    } finally {
        setConfirmando(false);
    }
    };

    const isServerError = status === 'error' && !isOffline;

    return (
    <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
        <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2 tracking-tight flex items-center gap-3">
            <ClipboardX className="w-7 h-7 text-text-muted" aria-hidden />
            Cancelaciones pendientes
        </h1>
        <p className="text-text-muted text-lg">
            Solicitudes enviadas por los clientes. Al confirmar, la orden pasa a Cancelado.
        </p>
        {status === 'success' && (
            <p className="text-sm text-text-muted mt-2" aria-live="polite">
            {solicitudes.length} {solicitudes.length === 1 ? 'solicitud pendiente' : 'solicitudes pendientes'}
            </p>
        )}
        </div>

        {actionError && (
        <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={handleRetry} />}>
            {actionError}
        </Alert>
        )}

        {isOffline && (
        <OfflineBanner message={error} onRetry={handleRetry} requestId={requestId} className="mb-6" />
        )}
        {isServerError && solicitudes.length > 0 && (
        <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={handleRetry} />}>
            {error} Se muestran los últimos datos disponibles.
        </Alert>
        )}

        {status === 'loading' ? (
        <div className="card p-16 flex justify-center">
            <LoadingState message="Cargando cancelaciones pendientes..." />
        </div>
        ) : isServerError && solicitudes.length === 0 ? (
        <div className="card p-8">
            <ErrorState
            title="No se pudieron cargar las cancelaciones pendientes"
            message={error}
            requestId={requestId}
            onRetry={handleRetry}
            />
        </div>
        ) : solicitudes.length === 0 ? (
        <div className="card p-8">
            <EmptyState
            icon={ClipboardX}
            title="No hay cancelaciones pendientes"
            description="Cuando un cliente solicite cancelar una orden, la solicitud aparecerá aquí para su revisión."
            />
        </div>
        ) : (
        <div className="card overflow-hidden">
            <Table>
            <TableHead className="border-b border-border-custom">
                <TableRow>
                <TableHeaderCell>Orden</TableHeaderCell>
                <TableHeaderCell>Cliente</TableHeaderCell>
                <TableHeaderCell>Estado al solicitar</TableHeaderCell>
                <TableHeaderCell>Motivo</TableHeaderCell>
                <TableHeaderCell>Solicitada</TableHeaderCell>
                <TableHeaderCell className="text-right">Acción</TableHeaderCell>
                </TableRow>
            </TableHead>
            <TableBody>
                {solicitudes.map((solicitud) => (
                <TableRow key={solicitud.id}>
                    <TableCell className="font-medium">
                    <Link
                        to={`/admin/ordenes/${solicitud.ordenId}`}
                        className="text-primary-blue no-underline hover:underline"
                    >
                        Orden n° {solicitud.ordenId}
                    </Link>
                    </TableCell>
                    <TableCell className="text-text-muted">
                    Cliente #{solicitud.clienteUsuarioId}
                    </TableCell>
                    <TableCell className="text-text-muted">
                    {ESTADOS_ORDEN[solicitud.estadoAlSolicitar] ?? `Estado ${solicitud.estadoAlSolicitar}`}
                    </TableCell>
                    <TableCell className="max-w-[280px] whitespace-pre-wrap break-words">
                    {solicitud.motivo}
                    </TableCell>
                    <TableCell className="text-text-muted whitespace-nowrap">
                    {formatDateTime(solicitud.solicitadaEn)}
                    </TableCell>
                    <TableCell className="text-right">
                    <Button
                        variant="danger"
                        className="whitespace-nowrap"
                        onClick={() => setSeleccionada(solicitud)}
                        disabled={confirmando}
                    >
                        Confirmar cancelación
                    </Button>
                    </TableCell>
                </TableRow>
                ))}
            </TableBody>
            </Table>
        </div>
        )}

        <ConfirmDialog
        open={seleccionada !== null}
        tone="danger"
        title="¿Confirmar la cancelación?"
        description={
            seleccionada
                ? `La orden n° ${seleccionada.ordenId} pasará a Cancelado. MS2 comprobará que no exista una aprobación del presupuesto antes de cancelarla.\nMotivo del cliente: ${seleccionada.motivo}`
                : ''
        }
        confirmLabel="Confirmar cancelación"
        isLoading={confirmando}
        onConfirm={confirmar}
        onCancel={() => setSeleccionada(null)}
        />
    </div>
    );
}
