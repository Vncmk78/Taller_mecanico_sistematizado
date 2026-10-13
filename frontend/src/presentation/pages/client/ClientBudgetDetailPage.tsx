import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, ClipboardX, FileText, Wrench, XCircle } from 'lucide-react';
import {
    type DecisionCliente,
    type ResultadoDecision,
    rechazoCancelaServicio,
    versionPendiente,
    versionVigente,
} from '@/domain/entities/Presupuesto';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { getApiErrorMessage, isConflictError } from '@/infrastructure/api/errors';
import { useBudgetStore } from '@/infrastructure/stores/useBudgetStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useBudgetDetail } from '@/presentation/hooks/useBudgetDetail';
import { ApproveBudgetDialog } from '@/presentation/components/budgets/ApproveBudgetDialog';
import { BudgetItemRow } from '@/presentation/components/budgets/BudgetItemRow';
import { BudgetStatusBadge } from '@/presentation/components/budgets/BudgetStatusBadge';
import { RejectBudgetDialog } from '@/presentation/components/budgets/RejectBudgetDialog';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { EFECTO_EN_ORDEN_LABEL, formatMoneyCLP } from '@/presentation/utils/budgetDisplay';

interface DecisionResuelta {
    tipo: DecisionCliente;
    resultado: ResultadoDecision;
}

export function ClientBudgetDetailPage() {
    const { ordenId } = useParams<{ ordenId: string }>();
    const { presupuesto, loading, notFound, failed, error, isOffline, requestId, refetch } =
        useBudgetDetail(ordenId);
    const order = useOrderStore((s) => s.orders.find((cached) => cached.id === ordenId));
    const updateBudget = useBudgetStore((s) => s.updateBudget);

    const [approveOpen, setApproveOpen] = useState(false);
    const [rejectOpen, setRejectOpen] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [decisionError, setDecisionError] = useState<string | null>(null);
    const [decisionResuelta, setDecisionResuelta] = useState<DecisionResuelta | null>(null);
    const [decisionVersion, setDecisionVersion] = useState<number | null>(null);

    const pendiente = presupuesto ? versionPendiente(presupuesto) : undefined;
    const cancelaServicio = presupuesto ? rechazoCancelaServicio(presupuesto) : false;
    const mostrada = pendiente ?? (presupuesto ? versionVigente(presupuesto) : undefined);
    const puedeAprobar = pendiente != null && !isOffline && pendiente.items.length > 0;
    const puedeRechazar = pendiente != null && !isOffline;

    const cerrarDialogos = () => {
        setApproveOpen(false);
        setRejectOpen(false);
    };

    const abrirDecision = (destino: DecisionCliente) => {
        if (!pendiente) return;
        setDecisionError(null);
        setDecisionVersion(pendiente.numero);
        if (destino === 'aprobado') setApproveOpen(true);
        else setRejectOpen(true);
    };

    const decidir = async (
        tipo: DecisionCliente,
        motivo?: string,
        confirmarCancelacion?: boolean
    ) => {
        if (submitting || !presupuesto) return;

        const actual = versionPendiente(presupuesto);
        const yaNoPendiente = 'Este presupuesto ya no está pendiente de su decisión. Actualizamos la información.';
        const versionCambio =
            'El presupuesto cambió mientras lo revisaba. Actualizamos la información; revise la versión vigente antes de decidir.';

        if (!actual) {
            setDecisionError(yaNoPendiente);
            cerrarDialogos();
            refetch();
            return;
        }
        if (decisionVersion !== null && actual.numero !== decisionVersion) {
            setDecisionError(versionCambio);
            cerrarDialogos();
            refetch();
            return;
        }

        setSubmitting(true);
        setDecisionError(null);
        try {
            const resultado = await presupuestoService.decidir(
                presupuesto.id,
                actual.numero,
                tipo,
                motivo,
                confirmarCancelacion
            );
            updateBudget(resultado.presupuesto);
            setDecisionResuelta({ tipo, resultado });
            cerrarDialogos();
        } catch (err) {
            if (isConflictError(err)) {
                setDecisionError(versionCambio);
                cerrarDialogos();
                refetch();
            } else {
                setDecisionError(getApiErrorMessage(err));
            }
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return <LoadingState message="Cargando presupuesto..." className="p-10" />;
    }

    if (failed) {
        return (
            <ErrorState
                className="p-10"
                title="No se pudo cargar el presupuesto"
                message={error}
                requestId={requestId}
                onRetry={refetch}
                action={
                    <Link
                        to="/client/presupuestos"
                        className="text-primary-blue text-sm font-medium no-underline hover:underline"
                    >
                        Volver a mis presupuestos
                    </Link>
                }
            />
        );
    }

    if (!presupuesto || notFound) {
        return (
            <EmptyState
                className="p-10"
                icon={ClipboardX}
                title="Presupuesto no encontrado."
                description="Es posible que esta orden todavía no tenga una cotización enviada por el taller."
                action={
                    <Link
                        to="/client/presupuestos"
                        className="text-primary-blue text-sm font-medium no-underline hover:underline"
                    >
                        Volver a mis presupuestos
                    </Link>
                }
            />
        );
    }

    const aplicacionPendiente =
        decisionResuelta?.resultado.efectoEnOrden != null &&
        !decisionResuelta.resultado.aplicacionConfirmada;

    return (
        <div className="p-5 sm:p-8 lg:p-10 animate-fade-in">
            <Link
                to="/client/presupuestos"
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a mis presupuestos
            </Link>

            {isOffline && <OfflineBanner message={error} onRetry={refetch} requestId={requestId} className="mb-6" />}

            {decisionResuelta && (
                <Alert
                    tone={decisionResuelta.tipo === 'aprobado' ? 'success' : 'warning'}
                    className="mb-6"
                >
                    {decisionResuelta.tipo === 'aprobado'
                        ? 'Presupuesto aprobado. El taller ha sido notificado.'
                        : 'Presupuesto rechazado. El taller ha sido notificado.'}
                    {decisionResuelta.resultado.efectoEnOrden &&
                        ` Estado del servicio: ${EFECTO_EN_ORDEN_LABEL[decisionResuelta.resultado.efectoEnOrden]}.`}
                    {aplicacionPendiente &&
                        ' La decisión quedó registrada; el estado del servicio se confirmará en breve.'}
                </Alert>
            )}

            <div className="flex flex-wrap justify-between items-center gap-4 mb-8">
                <div>
                    <h2 className="text-3xl font-bold mb-2 flex items-center gap-3">
                        <Wrench className="w-6 h-6 text-text-muted" aria-hidden />
                        Servicio n° {presupuesto.orderId}
                    </h2>
                    <p className="text-text-muted">
                        Versión {mostrada?.numero ?? presupuesto.ultimaVersion} de {presupuesto.cantidadVersiones} ·
                        Emitida el {formatDateTime(presupuesto.creadoEn)}
                    </p>
                </div>
                <BudgetStatusBadge estado={presupuesto.estadoUltimaVersion} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <section className="lg:col-span-2 card p-6">
                    <h3 className="text-xl font-bold flex items-center gap-2 mb-5 pb-4 border-b border-border-custom">
                        <FileText className="w-5 h-5 text-text-muted" aria-hidden />
                        Detalle del presupuesto
                    </h3>

                    {mostrada && mostrada.esModificacion && (
                        <Alert tone="info" className="mb-4">
                            Esta es una propuesta de modificación sobre una versión anterior.
                        </Alert>
                    )}

                    <div className="flex flex-col gap-3">
                        {mostrada?.items.map((item) => (
                            <BudgetItemRow key={item.id} item={item} />
                        ))}
                    </div>

                    <div className="flex justify-between items-center bg-bg-secondary rounded-xl px-5 py-4 mt-5">
                        <span className="text-lg text-text-muted">Costo Total Estimado:</span>
                        <span className="text-3xl font-bold">
                            {formatMoneyCLP(mostrada?.total ?? presupuesto.totalUltimaVersion)}
                        </span>
                    </div>

                    {mostrada?.decision && (
                        <p className="text-sm text-text-muted mt-4">
                            {mostrada.decision.decision === 'aprobado' ? 'Aprobado' : 'Rechazado'} el{' '}
                            {formatDateTime(mostrada.decision.fecha)}
                            {mostrada.decision.motivo ? ` · Motivo: ${mostrada.decision.motivo}` : ''}
                        </p>
                    )}
                </section>

                <section className="card p-6 flex flex-col">
                    <h3 className="text-xl font-bold mb-4">Su decisión</h3>

                    {pendiente ? (
                        <>
                            <p className="text-text-muted text-sm mb-6">
                                Revise las partidas y el total. Al aprobar, autoriza al taller a utilizar los
                                repuestos indicados y avanzar con la reparación.
                            </p>

                            {pendiente.items.length === 0 && (
                                <Alert tone="warning" className="mb-4">
                                    Este presupuesto no tiene partidas, por lo que no puede aprobarse.
                                    Contacte al taller o rechace la propuesta.
                                </Alert>
                            )}

                            {isOffline && (
                                <Alert tone="warning" className="mb-4">
                                    Sin conexión: para aprobar o rechazar el presupuesto necesita estar
                                    conectado. Reintente cuando recupere la conexión.
                                </Alert>
                            )}

                            {decisionError && (
                                <Alert tone="error" className="mb-4">
                                    {decisionError}
                                </Alert>
                            )}

                            <div className="mt-auto flex flex-col gap-3">
                                <Button
                                    variant="success"
                                    className="w-full py-3"
                                    disabled={!puedeAprobar}
                                    onClick={() => abrirDecision('aprobado')}
                                >
                                    <CheckCircle2 className="w-5 h-5 mr-2" aria-hidden />
                                    Aprobar Presupuesto
                                </Button>
                                <Button
                                    variant="danger"
                                    className="w-full py-3"
                                    disabled={!puedeRechazar}
                                    onClick={() => abrirDecision('rechazado')}
                                >
                                    <XCircle className="w-5 h-5 mr-2" aria-hidden />
                                    Rechazar
                                </Button>
                            </div>
                        </>
                    ) : (
                        <p className="text-text-muted text-sm">
                            {presupuesto.estadoUltimaVersion === 'aprobada'
                                ? 'Este presupuesto ya fue aprobado. El taller continúa con el servicio.'
                                : 'Este presupuesto fue rechazado. Contacte al taller si desea una nueva propuesta.'}
                        </p>
                    )}

                    <Link
                        to={`/client/ordenes/${presupuesto.orderId}`}
                        className="text-primary-blue text-sm font-medium no-underline hover:underline mt-6"
                    >
                        Ver seguimiento del servicio
                    </Link>
                </section>
            </div>

            {order && (
                <p className="text-sm text-text-muted mt-6">
                    Vehículo: {order.vehiculo ?? `N°${order.vehicleId}`}
                    {order.patente ? ` (${order.patente})` : ''}
                </p>
            )}

            {approveOpen && pendiente && (
                <ApproveBudgetDialog
                    total={pendiente.total}
                    cantidadPartidas={pendiente.items.length}
                    isLoading={submitting}
                    error={decisionError}
                    onConfirm={() => decidir('aprobado')}
                    onCancel={() => {
                        setApproveOpen(false);
                        setDecisionError(null);
                    }}
                />
            )}

            {rejectOpen && (
                <RejectBudgetDialog
                    cancelaServicio={cancelaServicio}
                    isLoading={submitting}
                    error={decisionError}
                    onConfirm={(motivo, confirmarCancelacion) =>
                        decidir('rechazado', motivo, confirmarCancelacion)
                    }
                    onCancel={() => {
                        setRejectOpen(false);
                        setDecisionError(null);
                    }}
                />
            )}
        </div>
    );
}
