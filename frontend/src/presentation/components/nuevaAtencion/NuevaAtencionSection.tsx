import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import {
    bloqueaNuevaSolicitud,
    DESCRIPCION_SOLICITUD_MAX,
    validarDescripcionSolicitud,
    type SolicitudNuevaAtencion,
} from '@/domain/entities/SolicitudNuevaAtencion';
import { esResultadoIncierto, getApiErrorMessage, isConflictError } from '@/infrastructure/api/errors';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { Textarea } from '@/presentation/components/ui/Textarea';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { hasAnyRole } from '@/presentation/utils/roleVisibility';
import { SituacionSolicitudBadge } from './SituacionSolicitudBadge';
import { RUTA_SOLICITUDES_CLIENTE, rutaOrdenDeSolicitud } from './rutasNuevaAtencion';

const CANCELADO = 8;
/** Solicitudes del antecedente que se consultan (las más recientes primero). */
const LIMITE_ANTECEDENTE = 20;

/**
 * - verificando: la respuesta se perdió y se consultan las solicitudes del antecedente.
 * - revisar: se pudo consultar; lo listado es lo que registra el servidor, sin
 *   atribuir ninguna solicitud a la petición fallida (pudo ser otra pestaña).
 * - sin_comprobar: tampoco se pudo consultar: resultado incierto.
 * En todos los casos el envío queda bloqueado hasta que el Cliente lo revise.
 */
type EstadoIncierto = 'verificando' | 'revisar' | 'sin_comprobar';

interface Resultado {
    tono: 'success' | 'info';
    texto: string;
    solicitudId: string;
}

interface NuevaAtencionSectionProps {
    order: Order;
    className?: string;
}

/**
 * Solicitud de nueva atención desde el detalle de una orden Cancelada del
 * portal Cliente (POST /api/ordenes/{id}/nueva-atencion). No reserva hora, no
 * crea una orden ni consume cupo; tampoco exige que el vehículo haya sido
 * devuelto. La propiedad y las reglas las decide MS2: aquí solo se orienta.
 */
export function NuevaAtencionSection({ order, className = '' }: NuevaAtencionSectionProps) {
    const user = useAuthStore((s) => s.user);
    const esCliente = hasAnyRole(user, 'cliente');
    const visible = esCliente && order.estadoCodigo === CANCELADO;

    const [solicitudes, setSolicitudes] = useState<SolicitudNuevaAtencion[]>([]);
    const [total, setTotal] = useState(0);
    const [cargando, setCargando] = useState(visible);
    const [errorLista, setErrorLista] = useState<string | null>(null);

    const [descripcion, setDescripcion] = useState('');
    const [errorDescripcion, setErrorDescripcion] = useState<string | null>(null);
    const [enviando, setEnviando] = useState(false);
    const enviandoRef = useRef(false);
    const [error, setError] = useState<string | null>(null);
    const [conflicto, setConflicto] = useState(false);
    const [resultado, setResultado] = useState<Resultado | null>(null);
    const [incierto, setIncierto] = useState<EstadoIncierto | null>(null);

    /** Consulta las solicitudes del antecedente. Devuelve false si falló. */
    const consultar = useCallback(async (): Promise<boolean> => {
        setCargando(true);
        try {
            const pagina = await nuevaAtencionService.listar(
                { ordenCanceladaId: order.id },
                { limit: LIMITE_ANTECEDENTE, offset: 0 }
            );
            setSolicitudes(pagina.items);
            setTotal(pagina.total);
            setErrorLista(null);
            return true;
        } catch (err) {
            setErrorLista(getApiErrorMessage(err, 'No se pudieron consultar las solicitudes de esta orden.'));
            return false;
        } finally {
            setCargando(false);
        }
    }, [order.id]);

    useEffect(() => {
        if (!visible) return;
        // Carga inicial desde la API (sistema externo); consultar marca la carga.
        // eslint-disable-next-line react/set-state-in-effect
        void consultar();
    }, [visible, consultar]);

    if (!visible) return null;

    const comprobar = async () => {
        setIncierto('verificando');
        const ok = await consultar();
        setIncierto(ok ? 'revisar' : 'sin_comprobar');
    };

    const enviar = async (event: FormEvent) => {
        event.preventDefault();
        if (enviandoRef.current || incierto !== null) return;
        const problema = validarDescripcionSolicitud(descripcion);
        setErrorDescripcion(problema);
        if (problema) return;

        enviandoRef.current = true;
        setEnviando(true);
        setError(null);
        setConflicto(false);
        setResultado(null);
        try {
            const { solicitud, creada } = await nuevaAtencionService.solicitar(order.id, descripcion);
            setDescripcion('');
            setResultado(
                creada
                    ? {
                          tono: 'success',
                          texto: `Solicitud n° ${solicitud.id} enviada. Queda pendiente de revisión del taller: no reserva una hora ni crea una orden.`,
                          solicitudId: solicitud.id,
                      }
                    : {
                          tono: 'info',
                          texto: `Ya existía una solicitud pendiente con la misma descripción (n° ${solicitud.id}); no se creó otra.`,
                          solicitudId: solicitud.id,
                      }
            );
            await consultar();
        } catch (err) {
            if (esResultadoIncierto(err)) {
                await comprobar();
            } else {
                setError(getApiErrorMessage(err, 'No fue posible enviar la solicitud.'));
                if (isConflictError(err)) setConflicto(true);
            }
        } finally {
            enviandoRef.current = false;
            setEnviando(false);
        }
    };

    const bloqueante = solicitudes.find(bloqueaNuevaSolicitud);
    const recortada = descripcion.trim();

    return (
        <section className={`card p-6 ${className}`} aria-labelledby={`nueva-atencion-${order.id}`}>
            <h3
                id={`nueva-atencion-${order.id}`}
                className="text-xl font-bold flex items-center gap-2 mb-4 pb-4 border-b border-border-custom"
            >
                <RotateCcw className="w-5 h-5 text-text-muted" aria-hidden />
                Nueva atención
            </h3>

            <p className="text-text-muted text-sm mb-4">
                Esta orden está cancelada y no se reabre. Puede pedir que el taller revise una nueva
                atención para el mismo vehículo: la solicitud no reserva una hora ni crea una orden, y
                no es necesario haber retirado el vehículo.
            </p>

            {resultado && (
                <Alert tone={resultado.tono} className="mb-4">
                    {resultado.texto}{' '}
                    <Link to={`${RUTA_SOLICITUDES_CLIENTE}/${resultado.solicitudId}`} className="underline">
                        Ver solicitud
                    </Link>
                </Alert>
            )}

            {error && (
                <Alert
                    tone="error"
                    className="mb-4"
                    action={
                        conflicto ? (
                            <Button
                                variant="secondary"
                                className="px-4 py-2 text-sm"
                                onClick={() => void consultar()}
                            >
                                Ver solicitudes de esta orden
                            </Button>
                        ) : undefined
                    }
                >
                    {error}
                </Alert>
            )}

            {incierto === 'verificando' && (
                <Alert tone="info" className="mb-4">
                    No se recibió la respuesta del servidor. Consultando las solicitudes registradas para
                    esta orden...
                </Alert>
            )}
            {(incierto === 'revisar' || incierto === 'sin_comprobar') && (
                <Alert tone="warning" className="mb-4">
                    {incierto === 'sin_comprobar'
                        ? 'Resultado incierto: no se recibió la respuesta y tampoco se pudieron consultar las solicitudes de esta orden. La solicitud pudo haberse registrado.'
                        : solicitudes.length === 0
                          ? 'No se recibió la respuesta y todavía no aparece ninguna solicitud para esta orden. Eso no prueba que no se haya guardado: el servidor podría seguir procesándola.'
                          : 'No se recibió la respuesta. Revise las solicitudes que registra el servidor para esta orden: pudieron originarse en esta u otra pestaña.'}
                    <span className="flex flex-wrap gap-2 mt-3">
                        <Button variant="secondary" className="px-4 py-2 text-sm" onClick={() => void comprobar()}>
                            Comprobar de nuevo
                        </Button>
                        <Button
                            variant="secondary"
                            className="px-4 py-2 text-sm"
                            onClick={() => setIncierto(null)}
                        >
                            Ya lo revisé: permitir enviar otra vez
                        </Button>
                    </span>
                </Alert>
            )}

            {cargando && incierto === null ? (
                <p className="text-text-muted text-sm" role="status">
                    Consultando solicitudes de esta orden...
                </p>
            ) : errorLista && incierto === null ? (
                <Alert
                    tone="error"
                    className="mb-4"
                    action={<RetryButton tone="error" onClick={() => void consultar()} />}
                >
                    {errorLista}
                </Alert>
            ) : null}

            {solicitudes.length > 0 && (
                <div className="mb-4">
                    <h4 className="text-sm font-semibold text-text-muted mb-2">
                        Solicitudes registradas para esta orden
                        {total > solicitudes.length ? ` (${solicitudes.length} más recientes de ${total})` : ''}
                    </h4>
                    <ul className="flex flex-col gap-2" aria-label={`Solicitudes de la orden ${order.id}`}>
                        {solicitudes.map((s) => (
                            <li key={s.id} className="bg-bg-secondary rounded-lg px-4 py-3">
                                <div className="flex items-center justify-between gap-3 flex-wrap">
                                    <Link
                                        to={`${RUTA_SOLICITUDES_CLIENTE}/${s.id}`}
                                        className="text-text-main font-semibold no-underline hover:underline"
                                    >
                                        Solicitud n° {s.id} · {formatDateTime(s.solicitadaEn)}
                                    </Link>
                                    <SituacionSolicitudBadge situacion={s.situacion} />
                                </div>
                                <p className="text-text-muted text-sm mt-1 line-clamp-2">{s.descripcion}</p>
                                {s.ordenGeneradaId && (
                                    <Link
                                        to={rutaOrdenDeSolicitud(s, s.ordenGeneradaId, user)}
                                        className="text-primary-blue text-sm font-medium no-underline hover:underline"
                                    >
                                        Ver orden generada n° {s.ordenGeneradaId}
                                    </Link>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {bloqueante ? (
                <Alert tone="info">
                    {bloqueante.situacion === 'pendiente'
                        ? `La solicitud n° ${bloqueante.id} está pendiente de revisión. No se puede enviar otra sobre esta orden mientras tanto.`
                        : bloqueante.ordenGeneradaId
                          ? `La solicitud n° ${bloqueante.id} fue aceptada y generó la orden n° ${bloqueante.ordenGeneradaId}. Si esa orden también se cancela, la próxima solicitud se hace desde ella.`
                          : `La solicitud n° ${bloqueante.id} fue aceptada. No se puede enviar otra sobre esta orden.`}
                </Alert>
            ) : (
                !cargando && (
                    <form onSubmit={enviar} noValidate aria-label="Solicitar nueva atención">
                        <Textarea
                            id={`nueva-atencion-descripcion-${order.id}`}
                            label="¿Qué necesita que revise el taller?"
                            value={descripcion}
                            rows={4}
                            onChange={(e) => {
                                setDescripcion(e.target.value);
                                if (errorDescripcion) setErrorDescripcion(null);
                            }}
                            hint={`${recortada.length}/${DESCRIPCION_SOLICITUD_MAX} caracteres`}
                            error={errorDescripcion ?? undefined}
                            required
                            containerClassName="mb-4"
                        />
                        <Button
                            type="submit"
                            isLoading={enviando}
                            disabled={incierto !== null}
                            className="self-start"
                        >
                            Enviar solicitud
                        </Button>
                    </form>
                )
            )}
        </section>
    );
}
