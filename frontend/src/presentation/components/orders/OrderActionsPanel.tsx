import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Wrench } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { ESTADOS_ORDEN, ordenStatusLabel } from '@/domain/entities/Order';
import {
    accionesDisponibles,
    type AccionOrden,
    type ActorOrden,
} from '@/domain/entities/OrderActions';
import type { UsuarioListado } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { orderService } from '@/infrastructure/api/OrderService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { useToast } from '@/presentation/components/ui/toastContext';

interface OrderActionsPanelProps {
    order: Order;
    className?: string;
}

const INPUT_CLASS =
    'w-full py-2.5 px-3 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue';

/**
 * Presenta las acciones habilitadas para el estado actual de la orden según el
 * rol de la sesión, usando el catálogo centralizado `accionesDisponibles`.
 *
 * Es el panel compartido por los portales de administrador y cliente (y el
 * detalle del mecánico); la vista de "Actualizar Estados" del mecánico conserva
 * su tarjeta con selector, que consume el mismo catálogo.
 */
export function OrderActionsPanel({ order, className }: OrderActionsPanelProps) {
    const user = useAuthStore((s) => s.user);

    const actor: ActorOrden | null = useMemo(
        () => (user ? { rol: user.role, userId: user.id } : null),
        [user]
    );
    const acciones = useMemo(
        () => (actor ? accionesDisponibles(order, actor) : []),
        [order, actor]
    );

    if (!actor || acciones.length === 0) return null;

    return (
        <OrderActionsPanelContent
            key={`${order.id}-${order.estadoCodigo}`}
            order={order}
            actor={actor}
            acciones={acciones}
            className={className}
        />
    );
}

interface OrderActionsPanelContentProps {
    order: Order;
    actor: ActorOrden;
    acciones: AccionOrden[];
    className?: string;
}

function OrderActionsPanelContent({ order, actor, acciones, className }: OrderActionsPanelContentProps) {
    const updateOrder = useOrderStore((s) => s.updateOrder);
    const isOffline = useOrderStore((s) => s.isOffline);
    const { showToast } = useToast();

    const [pending, setPending] = useState<AccionOrden | null>(null);
    const [destino, setDestino] = useState('');
    const [observacion, setObservacion] = useState('');
    const [motivo, setMotivo] = useState('');
    const [motivoError, setMotivoError] = useState('');
    const [mecanicoId, setMecanicoId] = useState('');
    const [mecanicos, setMecanicos] = useState<UsuarioListado[]>([]);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const requiereMecanicos = acciones.some((a) => a.id === 'asignar_mecanico');
    const [loadingMecanicos, setLoadingMecanicos] = useState(requiereMecanicos);

    useEffect(() => {
        if (!requiereMecanicos) return;
        let active = true;
        authService
            .listarUsuarios()
            .then((usuarios) => {
                if (!active) return;
                setMecanicos(usuarios.filter((u) => u.roles.includes('mecanico') && u.is_active));
            })
            .catch(() => {
                if (!active) return;
                setError('No se pudo cargar la lista de mecánicos.');
            })
            .finally(() => {
                if (active) setLoadingMecanicos(false);
            });
        return () => {
            active = false;
        };
    }, [requiereMecanicos]);

    const resetCampos = () => {
        setDestino('');
        setObservacion('');
        setMotivo('');
        setMotivoError('');
        setMecanicoId('');
    };

    const puedeConfirmar = (accion: AccionOrden) => {
        if (accion.id === 'avanzar_estado') return destino !== '';
        if (accion.id === 'asignar_mecanico') return !loadingMecanicos && mecanicoId !== '';
        return true;
    };

    const ejecutar = async () => {
        if (!pending || submitting) return;

        if (pending.id === 'avanzar_estado' && !destino) return;
        if (pending.id === 'asignar_mecanico' && !mecanicoId) return;
        if (pending.requiereMotivo && !motivo.trim()) {
            setMotivoError('Debe indicar un motivo.');
            return;
        }

        setSubmitting(true);
        setError('');
        try {
            let actualizada: Order;
            switch (pending.id) {
                case 'avanzar_estado':
                    actualizada = await orderService.cambiarEstado(
                        order.id,
                        Number(destino),
                        observacion
                    );
                    break;
                case 'asignar_mecanico':
                    actualizada = await orderService.asignarMecanico(
                        order.id,
                        mecanicoId,
                        observacion
                    );
                    break;
                case 'registrar_entrega':
                    actualizada = await orderService.registrarEntrega(order.id, observacion);
                    break;
                case 'cancelar':
                    actualizada =
                        actor.rol === 'cliente'
                            ? await orderService.cancelarComoCliente(order.id, motivo)
                            : await orderService.cambiarEstado(order.id, 8, motivo);
                    break;
                default:
                    return;
            }

            updateOrder(actualizada);
            showToast(
                `Orden n° ${order.id} actualizada a ${ordenStatusLabel(actualizada.estadoCodigo)}.`,
                'success'
            );
            setPending(null);
            resetCampos();
        } catch (err) {
            setError(getApiErrorMessage(err));
            setPending(null);
        } finally {
            setSubmitting(false);
        }
    };

    const abrir = (accion: AccionOrden) => {
        setError('');
        setMotivoError('');
        setPending(accion);
    };

    return (
        <section className={`card p-6 ${className ?? ''}`} aria-label="Acciones de la orden">
            <h3 className="text-xl font-bold flex items-center gap-2 mb-5 pb-4 border-b border-border-custom">
                <Wrench className="w-5 h-5 text-text-muted" aria-hidden />
                Acciones disponibles
            </h3>

            {error && (
                <Alert tone="error" className="mb-4">
                    {error}
                </Alert>
            )}

            {isOffline && (
                <Alert tone="warning" className="mb-4">
                    Sin conexión: para modificar el estado de la orden necesita estar conectado.
                    Restablezca la conexión e inténtelo nuevamente.
                </Alert>
            )}

            <div className="flex flex-col gap-5">
                {acciones.map((accion) => {
                    if (accion.id === 'decidir_presupuesto') {
                        return (
                            <div key={accion.id} className="flex flex-col gap-2">
                                <p className="text-text-muted text-sm">
                                    El presupuesto de esta orden está pendiente de su decisión.
                                </p>
                                <Link
                                    to={`/client/presupuestos/${order.id}`}
                                    className="text-primary-blue text-sm font-medium no-underline hover:underline"
                                >
                                    {accion.etiqueta}
                                </Link>
                            </div>
                        );
                    }

                    return (
                        <div
                            key={accion.id}
                            className="flex flex-col gap-3 pb-5 border-b border-border-custom last:border-b-0 last:pb-0"
                        >
                            {accion.id === 'avanzar_estado' && (
                                <label className="flex flex-col gap-1 text-sm">
                                    <span className="text-text-muted">Siguiente estado</span>
                                    <select
                                        id={`orden-${order.id}-${accion.id}-destino`}
                                        name="destino"
                                        value={destino}
                                        onChange={(e) => setDestino(e.target.value)}
                                        aria-label={`Siguiente estado de la orden ${order.id}`}
                                        aria-required="true"
                                        className={INPUT_CLASS}
                                    >
                                        <option value="">Seleccionar...</option>
                                        {accion.destinos.map((codigo) => (
                                            <option key={codigo} value={codigo}>
                                                {ESTADOS_ORDEN[codigo]}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                            )}

                            {accion.id === 'asignar_mecanico' && (
                                <label className="flex flex-col gap-1 text-sm">
                                    <span className="text-text-muted">Mecánico responsable</span>
                                    <select
                                        id={`orden-${order.id}-${accion.id}-mecanico`}
                                        name="mecanico"
                                        value={mecanicoId}
                                        onChange={(e) => setMecanicoId(e.target.value)}
                                        aria-label={`Mecánico para la orden ${order.id}`}
                                        aria-required="true"
                                        disabled={loadingMecanicos}
                                        className={INPUT_CLASS}
                                    >
                                        <option value="">
                                            {loadingMecanicos ? 'Cargando mecánicos...' : 'Seleccionar...'}
                                        </option>
                                        {mecanicos.map((m) => (
                                            <option key={m.id} value={m.id}>
                                                {m.full_name}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                            )}

                            {accion.requiereMotivo ? (
                                <label className="flex flex-col gap-1 text-sm">
                                    <span className="text-text-muted">Motivo (obligatorio)</span>
                                    <input
                                        id={`orden-${order.id}-${accion.id}-motivo`}
                                        type="text"
                                        name="motivo"
                                        value={motivo}
                                        onChange={(e) => {
                                            setMotivo(e.target.value);
                                            if (motivoError) setMotivoError('');
                                        }}
                                        placeholder="Explique el motivo de la cancelación..."
                                        aria-label={`Motivo de la orden ${order.id}`}
                                        aria-required="true"
                                        aria-invalid={motivoError ? true : undefined}
                                        aria-describedby={
                                            motivoError
                                                ? `orden-${order.id}-${accion.id}-motivo-error`
                                                : `orden-${order.id}-${accion.id}-motivo-hint`
                                        }
                                        className={INPUT_CLASS}
                                    />
                                    {motivoError ? (
                                        <p
                                            id={`orden-${order.id}-${accion.id}-motivo-error`}
                                            role="alert"
                                            className="text-sm text-status-red"
                                        >
                                            {motivoError}
                                        </p>
                                    ) : (
                                        <span
                                            id={`orden-${order.id}-${accion.id}-motivo-hint`}
                                            className="text-xs text-text-muted"
                                        >
                                            Obligatorio para cancelar la orden.
                                        </span>
                                    )}
                                </label>
                            ) : (
                                accion.id !== 'asignar_mecanico' && (
                                    <label className="flex flex-col gap-1 text-sm">
                                        <span className="text-text-muted">Observación (opcional)</span>
                                        <input
                                            id={`orden-${order.id}-${accion.id}-observacion`}
                                            type="text"
                                            name="observacion"
                                            value={observacion}
                                            onChange={(e) => setObservacion(e.target.value)}
                                            placeholder="Comentario..."
                                            aria-label={`Observación de la orden ${order.id}`}
                                            className={INPUT_CLASS}
                                        />
                                    </label>
                                )
                            )}

                            {accion.id === 'asignar_mecanico' && (
                                <label className="flex flex-col gap-1 text-sm">
                                    <span className="text-text-muted">Observación (opcional)</span>
                                    <input
                                        id={`orden-${order.id}-${accion.id}-observacion`}
                                        type="text"
                                        name="observacion"
                                        value={observacion}
                                        onChange={(e) => setObservacion(e.target.value)}
                                        placeholder="Comentario de la asignación..."
                                        aria-label={`Observación de la orden ${order.id}`}
                                        className={INPUT_CLASS}
                                    />
                                </label>
                            )}

                            <Button
                                variant={accion.id === 'cancelar' ? 'danger' : 'primary'}
                                disabled={!accion.habilitada || isOffline || !puedeConfirmar(accion)}
                                onClick={() => abrir(accion)}
                                className="self-start"
                            >
                                {accion.etiqueta}
                            </Button>
                        </div>
                    );
                })}
            </div>

            <ConfirmDialog
                open={pending !== null}
                tone={pending?.id === 'cancelar' ? 'danger' : 'primary'}
                title={tituloDialogo(pending)}
                description={descripcionDialogo(pending, order, { destino, motivo, mecanicos, mecanicoId })}
                confirmLabel={etiquetaConfirmar(pending)}
                isLoading={submitting}
                onConfirm={ejecutar}
                onCancel={() => setPending(null)}
            />
        </section>
    );
}

interface DescripcionContexto {
    destino: string;
    motivo: string;
    mecanicos: UsuarioListado[];
    mecanicoId: string;
}

function tituloDialogo(accion: AccionOrden | null): string {
    switch (accion?.id) {
        case 'asignar_mecanico':
            return '¿Confirmar la asignación?';
        case 'registrar_entrega':
            return '¿Registrar la entrega del vehículo?';
        case 'cancelar':
            return '¿Confirmar la cancelación?';
        default:
            return '¿Confirmar el avance de estado?';
    }
}

function etiquetaConfirmar(accion: AccionOrden | null): string {
    switch (accion?.id) {
        case 'asignar_mecanico':
            return 'Asignar mecánico';
        case 'registrar_entrega':
            return 'Registrar entrega';
        case 'cancelar':
            return 'Cancelar orden';
        default:
            return 'Avanzar estado';
    }
}

function descripcionDialogo(
    accion: AccionOrden | null,
    order: Order,
    ctx: DescripcionContexto
): string {
    if (!accion) return '';
    switch (accion.id) {
        case 'asignar_mecanico': {
            const nombre =
                ctx.mecanicos.find((m) => m.id === ctx.mecanicoId)?.full_name ?? 'el mecánico elegido';
            return `La orden n° ${order.id} quedará a cargo de ${nombre}.`;
        }
        case 'registrar_entrega':
            return `La orden n° ${order.id} pasará a Entregado. Confirme que el vehículo fue entregado al cliente.`;
        case 'cancelar':
            return `La orden n° ${order.id} pasará a Cancelado.${ctx.motivo ? `\nMotivo: ${ctx.motivo}` : ''}`;
        default:
            return `La orden n° ${order.id} pasará de ${ordenStatusLabel(order.estadoCodigo)} a ${
                ctx.destino ? ordenStatusLabel(Number(ctx.destino)) : ''
            }.`;
    }
}
