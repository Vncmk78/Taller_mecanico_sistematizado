import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardPlus } from 'lucide-react';
import { ordenStatusLabel } from '@/domain/entities/Order';
import {
    admiteGenerarOrden,
    type SolicitudNuevaAtencion,
} from '@/domain/entities/SolicitudNuevaAtencion';
import { esResultadoIncierto, getApiErrorMessage, isConflictError } from '@/infrastructure/api/errors';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { rutaOrdenAdmin } from './rutasNuevaAtencion';

/**
 * - verificando: la respuesta se perdió y se consulta el GET de la solicitud.
 * - vinculada: el servidor registra una orden vinculada; se muestra sin
 *   atribuirla a esta petición.
 * - sin_vinculo: todavía no aparece el vínculo; no prueba que la creación falló.
 * - sin_comprobar: tampoco se pudo consultar (resultado incierto).
 * Mientras dure, generar queda bloqueado hasta resolverlo o revisarlo.
 */
type Incierto = 'verificando' | 'vinculada' | 'sin_vinculo' | 'sin_comprobar';

interface Exito {
    texto: string;
    ordenId: string;
}

interface GenerarOrdenSolicitudPanelProps {
    solicitud: SolicitudNuevaAtencion;
    /** Muestra la solicitud que devolvió o registra el servidor. */
    alGenerar: (solicitud: SolicitudNuevaAtencion) => void;
    /** GET de la solicitud sin ocultar la pantalla; null si falló. */
    comprobar: () => Promise<SolicitudNuevaAtencion | null>;
}

/**
 * Genera la orden de una solicitud aceptada con su endpoint específico
 * (POST /api/ordenes/nuevas-atenciones/{id}/orden, body {}), nunca con
 * POST /ordenes. MS2 decide ingreso, cupo y estado; la web no reabre la
 * cancelada, no asigna mecánico ni exige una devolución previa.
 */
export function GenerarOrdenSolicitudPanel({ solicitud, alGenerar, comprobar }: GenerarOrdenSolicitudPanelProps) {
    const updateOrder = useOrderStore((s) => s.updateOrder);
    const [confirmando, setConfirmando] = useState(false);
    const [enviando, setEnviando] = useState(false);
    const enviandoRef = useRef(false);
    const [error, setError] = useState<string | null>(null);
    const [conflicto, setConflicto] = useState(false);
    const [exito, setExito] = useState<Exito | null>(null);
    const [incierto, setIncierto] = useState<Incierto | null>(null);

    const verificar = async () => {
        setIncierto('verificando');
        const actual = await comprobar();
        if (!actual) setIncierto('sin_comprobar');
        else setIncierto(actual.ordenGeneradaId ? 'vinculada' : 'sin_vinculo');
    };

    const generar = async () => {
        if (enviandoRef.current) return;
        enviandoRef.current = true;
        setEnviando(true);
        setError(null);
        setConflicto(false);
        setExito(null);
        try {
            const { solicitud: vinculada, orden, creada } = await nuevaAtencionService.generarOrden(solicitud.id);
            setConfirmando(false);
            updateOrder(orden);
            alGenerar(vinculada);
            // El estado viene del servidor: un reintento puede devolver una orden que ya avanzó.
            const estado = ordenStatusLabel(orden.estadoCodigo);
            setExito({
                ordenId: orden.id,
                texto: creada
                    ? `Se generó la orden n° ${orden.id} (estado ${estado}).`
                    : `La solicitud ya tenía la orden n° ${orden.id}; no se creó otra. Estado actual: ${estado}.`,
            });
        } catch (err) {
            setConfirmando(false);
            if (esResultadoIncierto(err)) {
                await verificar();
            } else {
                setError(getApiErrorMessage(err, 'No fue posible generar la orden.'));
                if (isConflictError(err)) setConflicto(true);
            }
        } finally {
            enviandoRef.current = false;
            setEnviando(false);
        }
    };

    const disponible = admiteGenerarOrden(solicitud);
    if (!disponible && !exito && !error && incierto === null) return null;

    return (
        <section className="card p-6 mt-6" aria-labelledby="generar-orden-titulo">
            <h2 id="generar-orden-titulo" className="text-lg font-semibold flex items-center gap-2 mb-4">
                <ClipboardPlus className="w-5 h-5 text-text-muted" aria-hidden />
                Orden de la nueva atención
            </h2>

            {exito && (
                <Alert tone="success" className="mb-4">
                    {exito.texto}{' '}
                    <Link to={rutaOrdenAdmin(exito.ordenId)} className="underline">
                        Abrir orden n° {exito.ordenId}
                    </Link>
                </Alert>
            )}

            {error && (
                <Alert
                    tone="error"
                    className="mb-4"
                    action={
                        conflicto ? (
                            <Button variant="secondary" className="px-4 py-2 text-sm" onClick={() => void comprobar()}>
                                Consultar la solicitud
                            </Button>
                        ) : undefined
                    }
                >
                    {error}
                </Alert>
            )}

            {incierto === 'verificando' && (
                <Alert tone="info" className="mb-4">
                    No se recibió la respuesta del servidor. Consultando si la solicitud ya tiene una orden
                    vinculada...
                </Alert>
            )}
            {incierto === 'vinculada' && solicitud.ordenGeneradaId && (
                <Alert tone="info" className="mb-4">
                    No se recibió la respuesta. Según el servidor, la solicitud está vinculada a la orden n°{' '}
                    {solicitud.ordenGeneradaId}.{' '}
                    <Link to={rutaOrdenAdmin(solicitud.ordenGeneradaId)} className="underline">
                        Abrir orden n° {solicitud.ordenGeneradaId}
                    </Link>
                </Alert>
            )}
            {(incierto === 'sin_vinculo' || incierto === 'sin_comprobar') && (
                <Alert tone="warning" className="mb-4">
                    {incierto === 'sin_vinculo'
                        ? 'No se recibió la respuesta y la solicitud todavía no muestra una orden vinculada. Eso no prueba que la creación falló: el servidor podría seguir procesándola.'
                        : 'Resultado incierto: no se recibió la respuesta y tampoco se pudo consultar la solicitud. La orden pudo haberse generado.'}
                    <span className="flex flex-wrap gap-2 mt-3">
                        <Button variant="secondary" className="px-4 py-2 text-sm" onClick={() => void verificar()}>
                            Comprobar de nuevo
                        </Button>
                        {incierto === 'sin_vinculo' && (
                            <Button variant="secondary" className="px-4 py-2 text-sm" onClick={() => setIncierto(null)}>
                                Ya lo revisé: permitir generar otra vez
                            </Button>
                        )}
                    </span>
                </Alert>
            )}

            {disponible && incierto !== 'vinculada' && (
                <div className="flex flex-col gap-4">
                    <p className="text-text-muted text-sm">
                        La solicitud está aceptada y todavía no tiene orden. La nueva orden nacerá en Recibido y
                        sin mecánico, vinculada a la solicitud y a la orden cancelada n° {solicitud.ordenCanceladaId},
                        que no se reabre. El servidor verifica el ingreso del vehículo, el cupo y que no tenga otra
                        orden activa.
                    </p>
                    <Button
                        className="self-start"
                        disabled={enviando || incierto !== null}
                        onClick={() => {
                            setError(null);
                            setConfirmando(true);
                        }}
                    >
                        Generar orden
                    </Button>
                </div>
            )}

            <ConfirmDialog
                open={confirmando}
                tone="primary"
                title="¿Generar la orden de esta nueva atención?"
                description={`Se creará una orden nueva para la solicitud n° ${solicitud.id}, en Recibido y sin mecánico. Si el vehículo sigue en el taller se usa su ingreso abierto; si no, el servidor registra uno nuevo y valida el cupo.`}
                confirmLabel="Generar orden"
                isLoading={enviando}
                onConfirm={generar}
                onCancel={() => {
                    if (!enviandoRef.current) setConfirmando(false);
                }}
            />
        </section>
    );
}
