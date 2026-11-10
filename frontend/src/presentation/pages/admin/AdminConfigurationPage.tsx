import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react';
import axios from 'axios';
import { CalendarCheck, Wrench } from 'lucide-react';
import type { CapacidadMecanicos, CupoDiarioIngresos } from '@/domain/entities/ConfiguracionTaller';
import type { UsuarioListado } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import { configuracionTallerService } from '@/infrastructure/api/ConfiguracionTallerService';
import { getApiErrorMessage, getApiErrorRequestId } from '@/infrastructure/api/errors';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { Input } from '@/presentation/components/ui/Input';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { useToast } from '@/presentation/components/ui/toastContext';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { formatJornada } from '@/presentation/utils/fechaJornada';

type Estado<T> =
    | { fase: 'cargando' }
    | { fase: 'error'; mensaje: string; requestId: string | null }
    | { fase: 'listo'; dato: T };

/** Mensaje de un rechazo al guardar. El 422 de Pydantic llega en inglés. */
function mensajeGuardado(error: unknown): string {
    if (axios.isAxiosError(error) && error.response?.status === 422) {
        return 'El máximo debe ser un número entero positivo.';
    }
    return getApiErrorMessage(error, 'No fue posible guardar la configuración.');
}

/**
 * Valida solo el formato del campo para ayudar al usuario. MS2 vuelve a validar
 * y es quien aplica el límite al registrar ingresos o asignaciones.
 */
function leerEnteroPositivo(valor: string): number | null {
    const numero = Number(valor);
    return valor.trim() !== '' && Number.isInteger(numero) && numero > 0 ? numero : null;
}

interface LimiteFormProps {
    etiqueta: string;
    valorActual: number | null;
    onGuardar: (valor: number) => Promise<void>;
}

function LimiteForm({ etiqueta, valorActual, onGuardar }: LimiteFormProps) {
    const [valor, setValor] = useState(valorActual === null ? '' : String(valorActual));
    const [guardando, setGuardando] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const enviar = async (e: FormEvent) => {
        e.preventDefault();
        if (guardando) return;
        const numero = leerEnteroPositivo(valor);
        if (numero === null) {
            setError('Ingrese un número entero mayor que 0.');
            return;
        }
        setGuardando(true);
        setError(null);
        try {
            await onGuardar(numero);
        } catch (err) {
            setError(mensajeGuardado(err));
        } finally {
            setGuardando(false);
        }
    };

    return (
        <form onSubmit={enviar} noValidate className="flex flex-wrap gap-3 items-start mt-4">
            <Input
                label={etiqueta}
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                value={valor}
                onChange={(e) => setValor(e.target.value)}
                error={error ?? undefined}
                containerClassName="flex-1 min-w-[180px]"
            />
            <Button type="submit" isLoading={guardando} className="mt-7">
                Guardar
            </Button>
        </form>
    );
}

function Tarjeta({ icono, titulo, descripcion, children }: {
    icono: ReactNode; titulo: string; descripcion: string; children: ReactNode;
}) {
    return (
        <section className="card p-6" aria-label={titulo}>
            <div className="flex items-center gap-3 mb-1">
                {icono}
                <h3 className="text-xl font-semibold">{titulo}</h3>
            </div>
            <p className="text-text-muted text-sm mb-4">{descripcion}</p>
            {children}
        </section>
    );
}

export function AdminConfigurationPage() {
    const { showToast } = useToast();
    const [cupo, setCupo] = useState<Estado<CupoDiarioIngresos>>({ fase: 'cargando' });
    const [capacidad, setCapacidad] = useState<Estado<CapacidadMecanicos>>({ fase: 'cargando' });
    const [usuarios, setUsuarios] = useState<UsuarioListado[]>([]);

    const nombre = (id: string | null) =>
        id === null ? null : (usuarios.find((u) => u.id === id)?.full_name ?? `usuario n° ${id}`);

    const cargarCupo = useCallback(async () => {
        try {
            setCupo({ fase: 'listo', dato: await configuracionTallerService.obtenerCupoDiario() });
        } catch (err) {
            setCupo({
                fase: 'error',
                mensaje: getApiErrorMessage(err, 'No se pudo consultar el cupo diario.'),
                requestId: getApiErrorRequestId(err),
            });
        }
    }, []);

    const cargarCapacidad = useCallback(async () => {
        try {
            setCapacidad({ fase: 'listo', dato: await configuracionTallerService.obtenerCapacidadMecanicos() });
        } catch (err) {
            setCapacidad({
                fase: 'error',
                mensaje: getApiErrorMessage(err, 'No se pudo consultar la capacidad de los mecánicos.'),
                requestId: getApiErrorRequestId(err),
            });
        }
    }, []);

    useEffect(() => {
        // Las cargas solo actualizan el estado después del await (no en el
        // render del efecto); mismo patrón que AdminThresholdPage.
        // eslint-disable-next-line react/set-state-in-effect
        void cargarCupo();
        // eslint-disable-next-line react/set-state-in-effect
        void cargarCapacidad();
        // Los nombres solo mejoran la lectura: si fallan se muestran los ids.
        authService.listarUsuarios().then(setUsuarios, () => setUsuarios([]));
    }, [cargarCupo, cargarCapacidad]);

    const guardarCupo = async (valor: number) => {
        const dato = await configuracionTallerService.configurarCupoDiario(valor);
        setCupo({ fase: 'listo', dato });
        showToast(`Máximo diario de ingresos actualizado a ${valor}.`, 'success');
    };

    const guardarCapacidad = async (valor: number) => {
        const dato = await configuracionTallerService.configurarCapacidadMecanicos(valor);
        setCapacidad({ fase: 'listo', dato });
        showToast(`Máximo de órdenes activas por mecánico actualizado a ${valor}.`, 'success');
    };

    const ultimaModificacion = (porId: string | null, en: string) =>
        porId === null ? null : (
            <p className="text-text-muted text-xs mt-2">
                Última modificación: {nombre(porId)}, {formatDateTime(en)}.
            </p>
        );

    return (
        <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
            <h2 className="text-3xl font-bold mb-2 tracking-tight">Capacidad del taller</h2>
            <p className="text-text-muted text-lg mb-6">
                Dos límites independientes que el sistema valida al registrar cada operación.
            </p>

            <div className="grid gap-6 lg:grid-cols-2">
                <Tarjeta
                    icono={<CalendarCheck className="w-6 h-6 text-primary-orange" aria-hidden />}
                    titulo="Ingresos físicos por jornada"
                    descripcion="Cuenta los vehículos recibidos hoy. Reasignar una orden o crear otra sobre un ingreso abierto no consume cupo, y cancelar no lo devuelve."
                >
                    {cupo.fase === 'cargando' && <LoadingState message="Consultando cupo..." />}
                    {cupo.fase === 'error' && (
                        <ErrorState title="No se pudo consultar el cupo" message={cupo.mensaje}
                            requestId={cupo.requestId} onRetry={() => { setCupo({ fase: 'cargando' }); void cargarCupo(); }} />
                    )}
                    {cupo.fase === 'listo' && (
                        <>
                            <dl className="grid grid-cols-2 gap-4">
                                <div>
                                    <dt className="text-text-muted text-sm">Máximo vigente</dt>
                                    <dd className="text-2xl font-bold">
                                        {cupo.dato.maxIngresosDiarios ?? 'Sin configurar'}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-text-muted text-sm">
                                        Ingresos del {formatJornada(cupo.dato.jornadaLocal)}
                                    </dt>
                                    <dd className="text-2xl font-bold">{cupo.dato.ingresosRegistrados}</dd>
                                </div>
                            </dl>
                            {cupo.dato.maxIngresosDiarios === null && (
                                <Alert tone="warning" className="mt-4">
                                    Mientras no se configure, no se pueden registrar ingresos ni crear órdenes.
                                </Alert>
                            )}
                            {cupo.dato.sobreLimite && (
                                <Alert tone="warning" className="mt-4">
                                    Los ingresos de hoy ya superan el máximo. Lo registrado se conserva; se
                                    rechazarán nuevos ingresos hasta mañana o hasta subir el límite.
                                </Alert>
                            )}
                            {ultimaModificacion(cupo.dato.actualizadoPorId, cupo.dato.actualizadoEn)}
                            <LimiteForm
                                key={`cupo-${cupo.dato.maxIngresosDiarios}`}
                                etiqueta="Nuevo máximo de ingresos por jornada"
                                valorActual={cupo.dato.maxIngresosDiarios}
                                onGuardar={guardarCupo}
                            />
                        </>
                    )}
                </Tarjeta>

                <Tarjeta
                    icono={<Wrench className="w-6 h-6 text-primary-orange" aria-hidden />}
                    titulo="Órdenes activas por mecánico"
                    descripcion="Cuenta las órdenes asignadas que no están Entregadas ni Canceladas. Una orden Recibida sin mecánico no ocupa capacidad."
                >
                    {capacidad.fase === 'cargando' && <LoadingState message="Consultando capacidad..." />}
                    {capacidad.fase === 'error' && (
                        <ErrorState title="No se pudo consultar la capacidad" message={capacidad.mensaje}
                            requestId={capacidad.requestId} onRetry={() => { setCapacidad({ fase: 'cargando' }); void cargarCapacidad(); }} />
                    )}
                    {capacidad.fase === 'listo' && (
                        <>
                            <dl>
                                <dt className="text-text-muted text-sm">Máximo vigente</dt>
                                <dd className="text-2xl font-bold">
                                    {capacidad.dato.maxOrdenesActivas ?? 'Sin configurar'}
                                </dd>
                            </dl>
                            {capacidad.dato.maxOrdenesActivas === null && (
                                <Alert tone="warning" className="mt-4">
                                    Mientras no se configure, no se pueden asignar ni reasignar mecánicos.
                                </Alert>
                            )}
                            {capacidad.dato.mecanicosSobreLimite.length > 0 && (
                                <Alert tone="warning" className="mt-4">
                                    <p>
                                        Estos mecánicos superan el máximo. Sus órdenes se conservan; no
                                        podrán recibir nuevas asignaciones hasta bajar su carga:
                                    </p>
                                    <ul className="list-disc ml-5 mt-1">
                                        {capacidad.dato.mecanicosSobreLimite.map((m) => (
                                            <li key={m.mecanicoId}>
                                                {nombre(m.mecanicoId)}: {m.ordenesActivas} órdenes activas
                                            </li>
                                        ))}
                                    </ul>
                                </Alert>
                            )}
                            {ultimaModificacion(capacidad.dato.actualizadoPorId, capacidad.dato.actualizadoEn)}
                            <LimiteForm
                                key={`capacidad-${capacidad.dato.maxOrdenesActivas}`}
                                etiqueta="Nuevo máximo de órdenes activas por mecánico"
                                valorActual={capacidad.dato.maxOrdenesActivas}
                                onGuardar={guardarCapacidad}
                            />
                        </>
                    )}
                </Tarjeta>
            </div>
        </div>
    );
}
