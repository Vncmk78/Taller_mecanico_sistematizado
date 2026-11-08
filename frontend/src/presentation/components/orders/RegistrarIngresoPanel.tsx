import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ClipboardPlus } from 'lucide-react';
import type { CupoDiarioIngresos } from '@/domain/entities/ConfiguracionTaller';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { configuracionTallerService } from '@/infrastructure/api/ConfiguracionTallerService';
import type { Order } from '@/domain/entities/Order';
import {
    esResultadoIncierto,
    getApiErrorMessage,
    getApiErrorRequestId,
} from '@/infrastructure/api/errors';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { Select } from '@/presentation/components/ui/Select';
import { useToast } from '@/presentation/components/ui/toastContext';

interface RegistrarIngresoPanelProps {
    /** Vehículo ya elegido (ficha del vehículo). Si falta, se ofrece un selector. */
    vehiculo?: Vehicle;
    className?: string;
}

const etiquetaVehiculo = (v: Vehicle) => `${v.patent} · ${v.brand} ${v.model}`;

/** Órdenes del vehículo justo antes de pedir la creación (la más reciente primero). */
interface Instantanea {
    total: number;
    ultimoId: string | null;
}

/**
 * - verificando: consultando el historial del vehículo.
 * - sin_confirmar: no se pudo consultar (o no hay instantánea previa).
 * - no_encontrada: aún no aparece una orden nueva; MS2 podría seguir procesando.
 * - por_revisar: aparecieron órdenes nuevas, pero nada prueba que sean las de
 *   esta petición (otra pestaña u otro administrador pudo crearlas).
 * En todos los casos la creación queda bloqueada hasta que el administrador
 * revise y lo indique.
 */
type EstadoIncierto = 'verificando' | 'sin_confirmar' | 'no_encontrada' | 'por_revisar';

/** Máximo de órdenes nuevas que se listan para revisión. */
const MAX_ORDENES_REVISION = 10;

async function tomarInstantanea(vehiculoId: string): Promise<Instantanea | null> {
    try {
        const pagina = await orderService.getVehicleOrderHistory(vehiculoId, { limit: 1, offset: 0 });
        return { total: pagina.total, ultimoId: pagina.items[0]?.id ?? null };
    } catch {
        return null;
    }
}

/**
 * Registro del ingreso físico y creación de la orden (POST /api/ordenes).
 *
 * La web no decide si hay cupo ni si el ingreso se reutiliza: solo informa el
 * uso del día y muestra lo que responde MS2, que valida el cupo y registra el
 * ingreso, la orden y su historial en una única transacción.
 */
export function RegistrarIngresoPanel({ vehiculo, className = '' }: RegistrarIngresoPanelProps) {
    const navigate = useNavigate();
    const { showToast } = useToast();
    const updateOrder = useOrderStore((s) => s.updateOrder);

    const [vehiculos, setVehiculos] = useState<Vehicle[]>([]);
    const [cargandoVehiculos, setCargandoVehiculos] = useState(!vehiculo);
    const [vehiculoId, setVehiculoId] = useState(vehiculo?.id ?? '');
    const [cupo, setCupo] = useState<CupoDiarioIngresos | null>(null);
    const [confirmando, setConfirmando] = useState(false);
    const [creando, setCreando] = useState(false);
    const [error, setError] = useState<{ mensaje: string; requestId: string | null } | null>(null);
    const enviando = useRef(false);
    const [incierto, setIncierto] = useState<{
        vehiculo: Vehicle;
        instantanea: Instantanea | null;
        estado: EstadoIncierto;
        nuevas: Order[];
    } | null>(null);

    useEffect(() => {
        let activo = true;
        // El uso del cupo es informativo: si no se puede consultar, se puede
        // intentar igual y MS2 responderá con el motivo si rechaza.
        configuracionTallerService.obtenerCupoDiario().then(
            (c) => activo && setCupo(c),
            () => activo && setCupo(null)
        );
        if (!vehiculo) {
            vehicleService
                .getAllVehicles()
                .then((lista) => activo && setVehiculos(lista))
                .catch(() => activo && setError({ mensaje: 'No se pudo cargar la lista de vehículos.', requestId: null }))
                .finally(() => activo && setCargandoVehiculos(false));
        }
        return () => {
            activo = false;
        };
    }, [vehiculo]);

    const elegido = vehiculo ?? vehiculos.find((v) => v.id === vehiculoId);

    /**
     * Tras un resultado incierto, consulta si aparecieron órdenes nuevas del
     * vehículo respecto de la instantánea previa. No reintenta la creación ni
     * atribuye esas órdenes a la petición fallida: solo las muestra.
     */
    const verificar = async (vehiculoAfectado: Vehicle, instantanea: Instantanea | null) => {
        const estado = (e: EstadoIncierto, nuevas: Order[] = []) =>
            setIncierto({ vehiculo: vehiculoAfectado, instantanea, estado: e, nuevas });
        estado('verificando');
        if (!instantanea) {
            estado('sin_confirmar');
            return;
        }
        try {
            const pagina = await orderService.getVehicleOrderHistory(vehiculoAfectado.id, {
                limit: MAX_ORDENES_REVISION,
                offset: 0,
            });
            const cantidadNuevas = pagina.total - instantanea.total;
            if (cantidadNuevas <= 0) {
                estado('no_encontrada');
                return;
            }
            // El historial viene de la más reciente a la más antigua.
            estado('por_revisar', pagina.items.slice(0, cantidadNuevas));
            // Un ingreso nuevo pudo consumir cupo: se actualiza el uso mostrado.
            configuracionTallerService.obtenerCupoDiario().then(setCupo, () => undefined);
        } catch {
            estado('sin_confirmar');
        }
    };

    const crear = async () => {
        if (!elegido || enviando.current) return;
        enviando.current = true;
        setCreando(true);
        setError(null);
        setIncierto(null);
        const instantanea = await tomarInstantanea(elegido.id);
        try {
            const orden = await orderService.crearOrden(elegido.id);
            updateOrder(orden);
            setConfirmando(false);
            showToast(
                `Orden n° ${orden.id} creada en Recibido para ${elegido.patent} (ingreso n° ${orden.ingresoId}).`,
                'success'
            );
            navigate(`/admin/ordenes/${orden.id}`);
        } catch (err) {
            setConfirmando(false);
            if (esResultadoIncierto(err)) {
                // La respuesta se perdió: MS2 pudo haber guardado la orden.
                await verificar(elegido, instantanea);
            } else {
                setError({
                    mensaje: getApiErrorMessage(err, 'No fue posible crear la orden.'),
                    requestId: getApiErrorRequestId(err),
                });
            }
        } finally {
            enviando.current = false;
            setCreando(false);
        }
    };

    return (
        <section className={`card p-6 ${className}`} aria-label="Registrar ingreso y crear orden">
            <h3 className="text-xl font-bold flex items-center gap-2 mb-2">
                <ClipboardPlus className="w-5 h-5 text-primary-orange" aria-hidden />
                Registrar ingreso y crear orden
            </h3>
            <p className="text-text-muted text-sm mb-4">
                La orden queda en Recibido y sin mecánico; la asignación se hace después, desde
                el detalle de la orden. Si el vehículo ya tiene un ingreso abierto, la nueva
                orden lo reutiliza y no consume otro cupo.
            </p>

            {cupo && (
                <p className="text-sm mb-4" aria-live="polite">
                    {cupo.maxIngresosDiarios === null ? (
                        <>
                            El máximo diario de ingresos no está configurado.{' '}
                            <Link to="/admin/configuracion" className="text-primary-blue font-medium">
                                Configurarlo
                            </Link>
                        </>
                    ) : (
                        <>
                            Ingresos de hoy: <strong>{cupo.ingresosRegistrados}</strong> de{' '}
                            <strong>{cupo.maxIngresosDiarios}</strong>.
                        </>
                    )}
                </p>
            )}

            {vehiculo ? (
                <p className="mb-4">
                    Vehículo: <strong>{etiquetaVehiculo(vehiculo)}</strong>
                </p>
            ) : (
                <Select
                    id="registrar-ingreso-vehiculo"
                    label="Vehículo registrado"
                    value={vehiculoId}
                    onChange={(e) => setVehiculoId(e.target.value)}
                    disabled={cargandoVehiculos}
                    aria-required="true"
                >
                    <option value="">{cargandoVehiculos ? 'Cargando vehículos...' : 'Seleccionar...'}</option>
                    {vehiculos.map((v) => (
                        <option key={v.id} value={v.id}>
                            {etiquetaVehiculo(v)}
                        </option>
                    ))}
                </Select>
            )}

            {incierto?.estado === 'verificando' && (
                <Alert tone="info" className="mb-4">
                    No llegó la respuesta del servidor. Revisando las órdenes de{' '}
                    {incierto.vehiculo.patent}...
                </Alert>
            )}
            {incierto && incierto.estado !== 'verificando' && (
                <Alert tone="warning" className="mb-4">
                    <p className="font-semibold">
                        No se pudo confirmar si se creó la orden de {incierto.vehiculo.patent}.
                    </p>
                    {incierto.estado === 'sin_confirmar' && (
                        <p className="mt-1">
                            Tampoco fue posible revisar sus órdenes. Revise las{' '}
                            <Link to={`/admin/vehiculos/${incierto.vehiculo.id}`} className="font-medium">
                                órdenes del vehículo
                            </Link>{' '}
                            antes de registrar otra vez.
                        </p>
                    )}
                    {incierto.estado === 'no_encontrada' && (
                        <p className="mt-1">
                            Todavía no aparece una orden nueva, pero el servidor podría seguir
                            procesándola. Compruebe de nuevo en unos segundos.
                        </p>
                    )}
                    {incierto.estado === 'por_revisar' && (
                        <>
                            <p className="mt-1">
                                Después del intento aparecieron estas órdenes del vehículo. No se puede
                                comprobar que alguna corresponda a esta solicitud: pudo crearlas otra
                                pestaña u otro administrador. Revíselas antes de registrar otra vez.
                            </p>
                            <ul className="list-disc ml-5 mt-1" aria-label="Órdenes nuevas para revisar">
                                {incierto.nuevas.map((o) => (
                                    <li key={o.id}>
                                        <Link to={`/admin/ordenes/${o.id}`} className="font-medium">
                                            Orden n° {o.id}
                                        </Link>
                                        , registrada por el usuario n° {o.creadoPorId} el{' '}
                                        {formatDateTime(o.creadoEn)}
                                    </li>
                                ))}
                            </ul>
                        </>
                    )}
                    <div className="flex flex-wrap gap-2 mt-3">
                        <Button
                            variant="secondary"
                            className="px-3 py-1.5 text-sm"
                            onClick={() => void verificar(incierto.vehiculo, incierto.instantanea)}
                        >
                            Comprobar de nuevo
                        </Button>
                        <Button
                            variant="secondary"
                            className="px-3 py-1.5 text-sm"
                            onClick={() => setIncierto(null)}
                        >
                            Ya lo revisé: permitir registrar otra vez
                        </Button>
                    </div>
                </Alert>
            )}

            {error && (
                <Alert tone="error" className="mb-4">
                    {error.mensaje}
                    {error.requestId && (
                        <span className="block text-xs mt-1">ID de solicitud: {error.requestId}</span>
                    )}
                </Alert>
            )}

            <Button
                variant="accent"
                // Mientras el resultado anterior siga incierto, crear otra vez podría
                // duplicar la orden: se exige que el administrador lo revise.
                disabled={!elegido || creando || incierto !== null}
                onClick={() => {
                    setError(null);
                    setConfirmando(true);
                }}
            >
                Registrar ingreso y crear orden
            </Button>

            <ConfirmDialog
                open={confirmando}
                tone="primary"
                title="¿Registrar el ingreso y crear la orden?"
                description={
                    elegido
                        ? `Se registrará hoy el ingreso físico de ${etiquetaVehiculo(elegido)} y se creará su orden en Recibido. ` +
                          'El ingreso cuenta para el cupo del día aunque la orden se cancele después.'
                        : ''
                }
                confirmLabel="Crear orden"
                isLoading={creando}
                onConfirm={() => void crear()}
                onCancel={() => setConfirmando(false)}
            />
        </section>
    );
}
