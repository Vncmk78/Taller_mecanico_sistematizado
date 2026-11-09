import { useRef, useState, type FormEvent } from 'react';
import { ClipboardCheck } from 'lucide-react';
import {
    admiteRevision,
    SITUACIONES_SOLICITUD,
    validarRespuestaRevision,
    type DecisionRevision,
    type SolicitudNuevaAtencion,
} from '@/domain/entities/SolicitudNuevaAtencion';
import { esResultadoIncierto, getApiErrorMessage, isConflictError } from '@/infrastructure/api/errors';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { Textarea } from '@/presentation/components/ui/Textarea';

/**
 * - verificando: la respuesta se perdió y se consulta el GET de la solicitud.
 * - revisada: el servidor ya la registra revisada; no se atribuye a esta
 *   petición (pudo hacerlo otro Administrador).
 * - pendiente: sigue pendiente; no prueba que el POST no se guardó.
 * - sin_comprobar: tampoco se pudo consultar (resultado incierto).
 */
type Incierto = 'verificando' | 'revisada' | 'pendiente' | 'sin_comprobar';

interface RevisionSolicitudPanelProps {
    solicitud: SolicitudNuevaAtencion;
    /** Muestra la solicitud que devolvió el servidor. */
    alRevisar: (solicitud: SolicitudNuevaAtencion) => void;
    /** GET de la solicitud sin ocultar la pantalla; null si falló. */
    comprobar: () => Promise<SolicitudNuevaAtencion | null>;
}

const DECISIONES: DecisionRevision[] = ['aceptada', 'rechazada'];

/**
 * Revisión administrativa de una solicitud pendiente
 * (POST /api/ordenes/nuevas-atenciones/{id}/revision). Solo envía decisión y
 * respuesta; responsable y fecha los registra MS2. Una revisión confirmada no
 * se edita: en ese caso esta sección no ofrece formulario y la auditoría se ve
 * en el detalle.
 */
export function RevisionSolicitudPanel({ solicitud, alRevisar, comprobar }: RevisionSolicitudPanelProps) {
    const [decision, setDecision] = useState<DecisionRevision | ''>('');
    const [respuesta, setRespuesta] = useState('');
    const [errorDecision, setErrorDecision] = useState<string | null>(null);
    const [errorRespuesta, setErrorRespuesta] = useState<string | null>(null);
    const [confirmando, setConfirmando] = useState(false);
    const [enviando, setEnviando] = useState(false);
    const enviandoRef = useRef(false);
    const [error, setError] = useState<string | null>(null);
    const [conflicto, setConflicto] = useState(false);
    const [exito, setExito] = useState<string | null>(null);
    const [incierto, setIncierto] = useState<Incierto | null>(null);

    const verificar = async () => {
        setIncierto('verificando');
        const actual = await comprobar();
        if (!actual) setIncierto('sin_comprobar');
        else setIncierto(actual.situacion === 'pendiente' ? 'pendiente' : 'revisada');
    };

    const solicitarConfirmacion = (event: FormEvent) => {
        event.preventDefault();
        if (incierto !== null) return;
        const sinDecision = decision === '' ? 'Elija aceptar o rechazar la solicitud.' : null;
        const problema = validarRespuestaRevision(respuesta);
        setErrorDecision(sinDecision);
        setErrorRespuesta(problema);
        if (sinDecision || problema) return;
        setError(null);
        setConfirmando(true);
    };

    const enviar = async () => {
        if (enviandoRef.current || decision === '') return;
        enviandoRef.current = true;
        setEnviando(true);
        setError(null);
        setConflicto(false);
        setExito(null);
        try {
            const revisada = await nuevaAtencionService.revisar(solicitud.id, decision, respuesta);
            setConfirmando(false);
            alRevisar(revisada);
            setExito(
                `El servidor registró la solicitud n° ${revisada.id} como ${SITUACIONES_SOLICITUD[revisada.situacion]}. La auditoría de la revisión se muestra en el detalle.`
            );
        } catch (err) {
            setConfirmando(false);
            if (esResultadoIncierto(err)) {
                await verificar();
            } else {
                setError(getApiErrorMessage(err, 'No fue posible registrar la revisión.'));
                if (isConflictError(err)) setConflicto(true);
            }
        } finally {
            enviandoRef.current = false;
            setEnviando(false);
        }
    };

    const pendiente = admiteRevision(solicitud);
    if (!pendiente && !exito && !error && incierto === null) return null;

    return (
        <section className="card p-6 mt-6" aria-labelledby="revision-solicitud-titulo">
            <h2 id="revision-solicitud-titulo" className="text-lg font-semibold flex items-center gap-2 mb-4">
                <ClipboardCheck className="w-5 h-5 text-text-muted" aria-hidden />
                Revisar solicitud
            </h2>

            {exito && (
                <Alert tone="success" className="mb-4">
                    {exito}
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
                    No se recibió la respuesta del servidor. Consultando la solicitud...
                </Alert>
            )}
            {incierto === 'revisada' && (
                <Alert tone="info" className="mb-4">
                    No se recibió la respuesta. Según el servidor, la solicitud ya figura{' '}
                    {SITUACIONES_SOLICITUD[solicitud.situacion]}: su respuesta, responsable y fecha se muestran
                    en el detalle. Pudo registrarla esta petición u otro Administrador.
                </Alert>
            )}
            {(incierto === 'pendiente' || incierto === 'sin_comprobar') && (
                <Alert tone="warning" className="mb-4">
                    {incierto === 'pendiente'
                        ? 'No se recibió la respuesta y la solicitud todavía figura pendiente. Eso no prueba que la revisión no se guardó: el servidor podría seguir procesándola.'
                        : 'Resultado incierto: no se recibió la respuesta y tampoco se pudo consultar la solicitud. La revisión pudo haberse registrado.'}
                    <span className="flex flex-wrap gap-2 mt-3">
                        <Button variant="secondary" className="px-4 py-2 text-sm" onClick={() => void verificar()}>
                            Comprobar de nuevo
                        </Button>
                        {incierto === 'pendiente' && (
                            <Button variant="secondary" className="px-4 py-2 text-sm" onClick={() => setIncierto(null)}>
                                Ya lo revisé: permitir enviar otra vez
                            </Button>
                        )}
                    </span>
                </Alert>
            )}

            {pendiente && incierto !== 'revisada' && (
                <form onSubmit={solicitarConfirmacion} noValidate aria-label="Revisión de la solicitud">
                    <fieldset className="mb-4">
                        <legend className="block mb-2 text-sm text-text-muted">Decisión</legend>
                        <div className="flex flex-wrap gap-4">
                            {DECISIONES.map((d) => (
                                <label key={d} className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="radio"
                                        name={`decision-solicitud-${solicitud.id}`}
                                        value={d}
                                        checked={decision === d}
                                        onChange={() => {
                                            setDecision(d);
                                            setErrorDecision(null);
                                        }}
                                    />
                                    {d === 'aceptada' ? 'Aceptar' : 'Rechazar'}
                                </label>
                            ))}
                        </div>
                        {errorDecision && (
                            <p role="alert" className="mt-1 text-sm text-status-red">
                                {errorDecision}
                            </p>
                        )}
                    </fieldset>
                    <Textarea
                        id={`respuesta-solicitud-${solicitud.id}`}
                        label="Respuesta para el cliente"
                        value={respuesta}
                        rows={4}
                        onChange={(e) => {
                            setRespuesta(e.target.value);
                            if (errorRespuesta) setErrorRespuesta(null);
                        }}
                        hint="Obligatoria para aceptar y para rechazar. Una revisión confirmada no se puede modificar."
                        error={errorRespuesta ?? undefined}
                        required
                        containerClassName="mb-4"
                    />
                    <Button type="submit" disabled={enviando || incierto !== null}>
                        Registrar revisión
                    </Button>
                </form>
            )}

            <ConfirmDialog
                open={confirmando}
                tone={decision === 'rechazada' ? 'danger' : 'primary'}
                title={decision === 'rechazada' ? '¿Rechazar la solicitud?' : '¿Aceptar la solicitud?'}
                description={`La solicitud n° ${solicitud.id} quedará ${
                    decision ? SITUACIONES_SOLICITUD[decision] : ''
                } con la respuesta indicada. El servidor registra el responsable y la fecha, y la revisión no se podrá modificar.${
                    decision === 'aceptada' ? ' Aceptar no crea la orden: se genera después, por separado.' : ''
                }`}
                confirmLabel={decision === 'rechazada' ? 'Rechazar solicitud' : 'Aceptar solicitud'}
                isLoading={enviando}
                onConfirm={enviar}
                onCancel={() => {
                    if (!enviandoRef.current) setConfirmando(false);
                }}
            />
        </section>
    );
}
