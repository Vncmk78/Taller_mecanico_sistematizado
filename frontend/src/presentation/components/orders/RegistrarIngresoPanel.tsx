import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ClipboardPlus } from 'lucide-react';
import type { CupoDiarioIngresos } from '@/domain/entities/ConfiguracionTaller';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { configuracionTallerService } from '@/infrastructure/api/ConfiguracionTallerService';
import { getApiErrorMessage, getApiErrorRequestId, isOfflineError } from '@/infrastructure/api/errors';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
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

    const crear = async () => {
        if (!elegido || enviando.current) return;
        enviando.current = true;
        setCreando(true);
        setError(null);
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
            setError({
                mensaje: isOfflineError(err)
                    ? 'No se pudo conectar con el servidor. La orden no se creó; intente nuevamente.'
                    : getApiErrorMessage(err, 'No fue posible crear la orden.'),
                requestId: getApiErrorRequestId(err),
            });
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
                disabled={!elegido || creando}
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
