import { useCallback, useEffect, useRef, useState } from 'react';
import { PackageCheck } from 'lucide-react';
import type {
    DisponibilidadRepuesto,
    ResultadoDisponibilidad,
} from '@/domain/entities/Inventario';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import {
    esResultadoIncierto,
    getApiErrorMessage,
    getApiErrorRequestId,
    isOfflineError,
} from '@/infrastructure/api/errors';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';

interface FaltanteStockApi {
    repuesto_id: number;
    nombre: string;
    solicitado: number;
    disponible: number;
    faltan: number;
}

interface ErrorConRespuesta {
    response?: {
        status?: number;
        data?: {
            faltantes?: FaltanteStockApi[];
            detail?: string | { faltantes?: FaltanteStockApi[] };
        };
    };
}

/** Extrae los faltantes tanto del `RechazoStock` directo como del `detail` de la Gateway. */
function leerFaltantes(error: unknown): FaltanteStockApi[] {
    const data = (error as ErrorConRespuesta)?.response?.data;
    if (Array.isArray(data?.faltantes)) return data.faltantes;
    const anidados = typeof data?.detail === 'object' ? data.detail?.faltantes : undefined;
    return Array.isArray(anidados) ? anidados : [];
}

function estadoHttp(error: unknown): number | undefined {
    return (error as ErrorConRespuesta)?.response?.status;
}

/** Máximo que la orden puede consumir de un repuesto según el presupuesto y el stock. */
function maximoConsumible(repuesto: DisponibilidadRepuesto): number {
    return Math.max(0, Math.min(repuesto.requerido, repuesto.disponible));
}

interface ConsumoRepuestosPanelProps {
    orderId: string | number;
    /** Se invoca tras un consumo aplicado para refrescar la orden y el historial. */
    onConsumed?: () => void | Promise<void>;
    className?: string;
}

/**
 * Registra el consumo de los repuestos del presupuesto aprobado de una orden.
 *
 * La disponibilidad que expone MS3 ya descuenta lo consumido, así que cada
 * fila muestra lo que falta usar. El envío exige cantidades enteras dentro de
 * lo requerido y disponible, usa una `clave_operacion` idempotente (se conserva
 * ante fallos inciertos para que reintentar no descuente dos veces) y traduce
 * el 409 con `faltantes` sin perder lo ya escrito.
 */
export function ConsumoRepuestosPanel({
    orderId,
    onConsumed,
    className = '',
}: ConsumoRepuestosPanelProps) {
    const orderIdNumerico = Number(orderId);
    const [disponibilidad, setDisponibilidad] = useState<ResultadoDisponibilidad | null>(null);
    const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
    const [error, setError] = useState<string | null>(null);
    const [requestId, setRequestId] = useState<string | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [sinPresupuesto, setSinPresupuesto] = useState(false);

    const [cantidades, setCantidades] = useState<Record<number, string>>({});
    const [erroresCampo, setErroresCampo] = useState<Record<number, string>>({});
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

    // Se conserva entre reintentos para que MS3 devuelva lo ya aplicado en vez
    // de descontar de nuevo; solo se descarta cuando el rechazo es definitivo.
    const claveRef = useRef<string | null>(null);

    const cargar = useCallback(async () => {
        setStatus('loading');
        setError(null);
        setRequestId(null);
        setIsOffline(false);
        setSinPresupuesto(false);
        try {
            const resultado = await inventarioService.getDisponibilidadOrden(orderIdNumerico);
            setDisponibilidad(resultado);
            setStatus('success');
        } catch (err) {
            // 409: la orden no tiene presupuesto aprobado del que sacar los repuestos.
            if (estadoHttp(err) === 409) {
                setDisponibilidad(null);
                setSinPresupuesto(true);
                setStatus('success');
                return;
            }
            setDisponibilidad(null);
            setError(
                getApiErrorMessage(
                    err,
                    'No se pudo cargar la disponibilidad de repuestos de la orden.'
                )
            );
            setIsOffline(isOfflineError(err));
            setRequestId(getApiErrorRequestId(err));
            setStatus('error');
        }
    }, [orderIdNumerico]);

    useEffect(() => {
        // eslint-disable-next-line react/set-state-in-effect
        void cargar();
    }, [cargar]);

    const refrescarDisponibilidad = async () => {
        try {
            setDisponibilidad(await inventarioService.getDisponibilidadOrden(orderIdNumerico));
            setSinPresupuesto(false);
        } catch {
            // El consumo ya se aplicó; se conserva el detalle anterior si el
            // refresco de stock falla.
        }
    };

    const repuestosPendientes = (disponibilidad?.repuestos ?? []).filter(
        (repuesto) => repuesto.requerido > 0
    );

    const consumir = async () => {
        if (submitting) return;

        const nuevosErrores: Record<number, string> = {};
        const items: Array<{ repuestoId: number; cantidad: number }> = [];

        for (const repuesto of repuestosPendientes) {
            const valor = (cantidades[repuesto.repuestoId] ?? '').trim();
            if (valor === '') continue;

            const maximo = maximoConsumible(repuesto);
            if (!/^\d+$/.test(valor) || Number(valor) < 1) {
                nuevosErrores[repuesto.repuestoId] = 'Ingrese una cantidad entera de al menos 1.';
                continue;
            }
            if (Number(valor) > maximo) {
                nuevosErrores[repuesto.repuestoId] =
                    maximo === 0
                        ? 'No hay stock disponible para la orden.'
                        : `Puede consumir como máximo ${maximo}.`;
                continue;
            }
            items.push({ repuestoId: repuesto.repuestoId, cantidad: Number(valor) });
        }

        setErroresCampo(nuevosErrores);
        setSubmitError(null);
        setSuccess(null);

        if (Object.keys(nuevosErrores).length > 0) return;
        if (items.length === 0) {
            setSubmitError('Indique la cantidad de al menos un repuesto para registrar el consumo.');
            return;
        }

        setSubmitting(true);
        const clave = claveRef.current ?? crypto.randomUUID();
        claveRef.current = clave;

        try {
            const resultado = await inventarioService.consumir(orderIdNumerico, items, clave);
            claveRef.current = null;
            setCantidades({});
            setSuccess(
                resultado.repetido
                    ? 'El consumo ya estaba registrado; no se descontó dos veces.'
                    : `Consumo registrado para ${items.length} ${items.length === 1 ? 'repuesto' : 'repuestos'}.`
            );
            await refrescarDisponibilidad();
            try {
                await onConsumed?.();
            } catch {
                // El consumo ya quedó aplicado; el refresco de la orden es accesorio.
            }
        } catch (err) {
            const faltantes = leerFaltantes(err);
            if (estadoHttp(err) === 409 && faltantes.length > 0) {
                claveRef.current = null;
                setSubmitError(
                    `Stock insuficiente: ${faltantes
                        .map(
                            (faltante) =>
                                `${faltante.nombre} (solicitado ${faltante.solicitado}, disponible ${faltante.disponible}, faltan ${faltante.faltan})`
                        )
                        .join(', ')}. No se descontó ningún repuesto.`
                );
                await refrescarDisponibilidad();
            } else if (esResultadoIncierto(err)) {
                // La clave se conserva: si el consumo sí se aplicó, el reintento
                // devuelve lo mismo con `repetido: true` en lugar de duplicarlo.
                setSubmitError(
                    `${getApiErrorMessage(
                        err,
                        'No se pudo confirmar el consumo de repuestos.'
                    )} La operación pudo quedar registrada; reintentar con los mismos datos es seguro.`
                );
            } else {
                claveRef.current = null;
                setSubmitError(getApiErrorMessage(err, 'No se pudo registrar el consumo de repuestos.'));
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <section className={`card p-6 mt-6 ${className}`.trim()} aria-labelledby="consumo-repuestos-title">
            <h3
                id="consumo-repuestos-title"
                className="text-xl font-semibold mb-2 flex items-center gap-2"
            >
                <PackageCheck className="h-5 w-5 text-text-muted" aria-hidden />
                Consumo de repuestos
            </h3>
            <p className="text-sm text-text-muted mb-4">
                Descuenta del stock los repuestos usados en la orden. Se toma primero lo
                reservado por esta orden y nunca lo reservado por otras.
            </p>

            {submitError && (
                <Alert tone="error" className="mb-4">
                    {submitError}
                </Alert>
            )}
            {success && (
                <Alert tone="success" className="mb-4">
                    {success}
                </Alert>
            )}

            {status === 'loading' ? (
                <LoadingState message="Cargando repuestos pendientes..." />
            ) : status === 'error' ? (
                <ErrorState
                    title="No se pudo cargar la disponibilidad de repuestos"
                    message={error}
                    requestId={requestId}
                    onRetry={() => void cargar()}
                />
            ) : sinPresupuesto ? (
                <Alert tone="warning">
                    La orden no tiene un presupuesto aprobado del que obtener los repuestos a
                    consumir.
                </Alert>
            ) : repuestosPendientes.length === 0 ? (
                <Alert tone="success">
                    No quedan repuestos pendientes de consumir del presupuesto aprobado.
                </Alert>
            ) : (
                <>
                    <ul className="space-y-3 mb-5">
                        {repuestosPendientes.map((repuesto) => {
                            const maximo = maximoConsumible(repuesto);
                            const errorCampo = erroresCampo[repuesto.repuestoId];
                            const inputId = `consumo-repuesto-${repuesto.repuestoId}`;
                            return (
                                <li
                                    key={repuesto.repuestoId}
                                    className="flex flex-wrap items-end justify-between gap-4 border-b border-border-custom pb-3 last:border-b-0"
                                >
                                    <div className="min-w-0">
                                        <p className="font-medium text-text-main">{repuesto.nombre}</p>
                                        <p className="text-sm text-text-muted">
                                            Pendiente del presupuesto: {repuesto.requerido} · Disponible
                                            para la orden: {repuesto.disponible}
                                            {repuesto.reservadoParaOrden > 0 &&
                                                ` (reservado: ${repuesto.reservadoParaOrden})`}
                                        </p>
                                    </div>
                                    <div className="w-40">
                                        <label
                                            htmlFor={inputId}
                                            className="block mb-1 text-xs text-text-muted"
                                        >
                                            Cantidad a consumir
                                        </label>
                                        <input
                                            id={inputId}
                                            type="number"
                                            min={1}
                                            max={maximo}
                                            step={1}
                                            inputMode="numeric"
                                            aria-label={`Cantidad de ${repuesto.nombre}`}
                                            aria-invalid={errorCampo ? true : undefined}
                                            aria-describedby={errorCampo ? `${inputId}-error` : undefined}
                                            className={`w-full py-2.5 px-3 bg-surface border rounded-lg text-text-main text-base outline-none focus:border-primary-blue focus:shadow-[0_0_0_3px_rgba(21,40,63,0.15)] ${
                                                errorCampo ? 'border-status-red' : 'border-border-custom'
                                            }`}
                                            value={cantidades[repuesto.repuestoId] ?? ''}
                                            disabled={submitting || maximo === 0}
                                            onChange={(event) => {
                                                const valor = event.target.value;
                                                setCantidades((prev) => ({
                                                    ...prev,
                                                    [repuesto.repuestoId]: valor,
                                                }));
                                                setErroresCampo((prev) => {
                                                    if (!prev[repuesto.repuestoId]) return prev;
                                                    const siguiente = { ...prev };
                                                    delete siguiente[repuesto.repuestoId];
                                                    return siguiente;
                                                });
                                            }}
                                        />
                                        {errorCampo && (
                                            <p
                                                id={`${inputId}-error`}
                                                role="alert"
                                                className="mt-1 text-sm text-status-red"
                                            >
                                                {errorCampo}
                                            </p>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>

                    <div className="flex flex-wrap items-center gap-3">
                        <Button
                            variant="success"
                            onClick={() => void consumir()}
                            isLoading={submitting}
                        >
                            Registrar consumo
                        </Button>
                        <span className="text-sm text-text-muted">
                            {isOffline
                                ? 'Sin conexión: no se puede registrar el consumo.'
                                : 'La operación es todo o nada: si falta stock no se descuenta nada.'}
                        </span>
                    </div>
                </>
            )}
        </section>
    );
}
