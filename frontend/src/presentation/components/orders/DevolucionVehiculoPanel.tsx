import { useRef, useState } from 'react';
import { PackageCheck } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { puedeRegistrarDevolucion } from '@/domain/entities/OrderActions';
import { esResultadoIncierto, getApiErrorMessage } from '@/infrastructure/api/errors';
import { orderService } from '@/infrastructure/api/OrderService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { useToast } from '@/presentation/components/ui/toastContext';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { getUserRoles } from '@/presentation/utils/roleVisibility';

const CANCELADO = 8;

interface DevolucionVehiculoPanelProps {
    order: Order;
    className?: string;
}

/**
 * - verificando: la respuesta se perdió y se consulta el detalle de la orden.
 * - no_figura: el detalle aún no muestra la devolución; MS2 podría seguir
 *   procesándola.
 * - sin_comprobar: tampoco se pudo consultar el detalle (resultado incierto).
 */
type Comprobacion = 'verificando' | 'no_figura' | 'sin_comprobar';

/**
 * Devolución física del vehículo de una orden Cancelada
 * (POST /api/ordenes/{id}/devolucion, solo Administrador).
 *
 * La web no decide la fecha, el responsable ni el cierre del ingreso: los
 * registra MS2 y esta sección muestra lo que devuelve. La orden sigue
 * Cancelada. Repetir el registro es seguro: MS2 conserva los datos originales.
 */
export function DevolucionVehiculoPanel({ order, className = '' }: DevolucionVehiculoPanelProps) {
    const user = useAuthStore((s) => s.user);
    const updateOrder = useOrderStore((s) => s.updateOrder);
    const isOffline = useOrderStore((s) => s.isOffline);
    const { showToast } = useToast();

    const [confirmando, setConfirmando] = useState(false);
    const [enviando, setEnviando] = useState(false);
    const enviandoRef = useRef(false);
    const [error, setError] = useState('');
    const [comprobacion, setComprobacion] = useState<Comprobacion | null>(null);
    const [aviso, setAviso] = useState('');

    const roles = getUserRoles(user);
    if (order.estadoCodigo !== CANCELADO || !roles.includes('administrador')) return null;

    const comprobar = async () => {
        setComprobacion('verificando');
        setAviso('');
        try {
            const actual = await orderService.getOrderById(order.id);
            updateOrder(actual);
            if (actual.devueltoEn) {
                setComprobacion(null);
                setError('');
                setAviso(
                    'No se recibió la respuesta del registro, pero al consultar la orden la devolución figura registrada con estos datos.'
                );
            } else {
                setComprobacion(actual.devueltoEn === null ? 'no_figura' : 'sin_comprobar');
            }
        } catch {
            setComprobacion('sin_comprobar');
        }
    };

    const registrar = async () => {
        if (enviandoRef.current) return;
        enviandoRef.current = true;
        setEnviando(true);
        setError('');
        setAviso('');
        setComprobacion(null);
        try {
            const actualizada = await orderService.registrarDevolucion(order.id);
            updateOrder(actualizada);
            setConfirmando(false);
            showToast(`Devolución del vehículo de la orden n° ${order.id} registrada.`, 'success');
        } catch (err) {
            setConfirmando(false);
            if (esResultadoIncierto(err)) {
                await comprobar();
            } else {
                setError(getApiErrorMessage(err, 'No fue posible registrar la devolución.'));
            }
        } finally {
            enviandoRef.current = false;
            setEnviando(false);
        }
    };

    const registrada = typeof order.devueltoEn === 'string' && order.devueltoEn !== '';
    const desconocida = order.devueltoEn === undefined;
    const ofrecer = puedeRegistrarDevolucion(order, roles);

    return (
        <section
            className={`card p-6 ${className}`}
            aria-labelledby={`devolucion-orden-${order.id}`}
        >
            <h3
                id={`devolucion-orden-${order.id}`}
                className="text-xl font-bold flex items-center gap-2 mb-4 pb-4 border-b border-border-custom"
            >
                <PackageCheck className="w-5 h-5 text-text-muted" aria-hidden />
                Devolución del vehículo
            </h3>

            {registrada ? (
                <div className="flex flex-col gap-3">
                    {aviso && <Alert tone="info">{aviso}</Alert>}
                    <p className="text-text-main">
                        Vehículo devuelto el{' '}
                        <strong>{formatDateTime(order.devueltoEn as string)}</strong>. Registrada por el
                        usuario n° <strong>{order.devueltoPorId}</strong>.
                    </p>
                    <p className="text-text-muted text-sm">La orden se mantiene Cancelada.</p>
                </div>
            ) : desconocida ? (
                <div className="flex flex-col gap-3">
                    <Alert tone="warning">
                        El servidor no informó si el vehículo ya fue devuelto. Consulte la orden de nuevo
                        antes de registrar la devolución.
                    </Alert>
                    <Button
                        variant="secondary"
                        className="self-start"
                        isLoading={comprobacion === 'verificando'}
                        onClick={comprobar}
                    >
                        Consultar de nuevo
                    </Button>
                </div>
            ) : (
                <div className="flex flex-col gap-4">
                    <p className="text-text-muted text-sm">
                        La orden fue cancelada y el vehículo aún no figura como devuelto. Registre la
                        devolución cuando el cliente lo retire; la orden seguirá Cancelada.
                    </p>

                    {error && <Alert tone="error">{error}</Alert>}

                    {comprobacion === 'verificando' && (
                        <Alert tone="info">
                            No se recibió la respuesta del servidor. Comprobando si la devolución quedó
                            registrada...
                        </Alert>
                    )}
                    {comprobacion === 'no_figura' && (
                        <Alert
                            tone="warning"
                            action={
                                <Button variant="secondary" className="px-4 py-2 text-sm" onClick={comprobar}>
                                    Comprobar de nuevo
                                </Button>
                            }
                        >
                            No se recibió la respuesta y la devolución todavía no figura registrada. El
                            servidor podría seguir procesándola: compruebe de nuevo en unos segundos.
                            Repetir el registro es seguro, porque el servidor conserva la fecha y el
                            responsable originales.
                        </Alert>
                    )}
                    {comprobacion === 'sin_comprobar' && (
                        <Alert
                            tone="warning"
                            action={
                                <Button variant="secondary" className="px-4 py-2 text-sm" onClick={comprobar}>
                                    Comprobar de nuevo
                                </Button>
                            }
                        >
                            Resultado incierto: no se recibió la respuesta y tampoco se pudo consultar la
                            orden. La devolución pudo haberse registrado; compruébelo antes de continuar.
                        </Alert>
                    )}

                    {isOffline && (
                        <Alert tone="warning">
                            Sin conexión: para registrar la devolución necesita estar conectado.
                        </Alert>
                    )}

                    {ofrecer && (
                        <Button
                            variant="primary"
                            className="self-start"
                            disabled={enviando || comprobacion === 'verificando' || isOffline}
                            onClick={() => {
                                setError('');
                                setConfirmando(true);
                            }}
                        >
                            Registrar devolución
                        </Button>
                    )}
                </div>
            )}

            <ConfirmDialog
                open={confirmando}
                tone="primary"
                title="¿Registrar la devolución del vehículo?"
                description={`Se registrará que el vehículo de la orden n° ${order.id} fue devuelto al cliente. La orden seguirá Cancelada. La fecha y el responsable los registra el servidor.`}
                confirmLabel="Registrar devolución"
                isLoading={enviando}
                onConfirm={registrar}
                onCancel={() => {
                    if (!enviandoRef.current) setConfirmando(false);
                }}
            />
        </section>
    );
}
