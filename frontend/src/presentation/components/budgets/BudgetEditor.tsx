import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Plus, Send } from 'lucide-react';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { AplicacionPresupuestoPendienteError } from '@/domain/ports/PresupuestoPort';
import { aplicacionPendiente } from '@/domain/entities/Presupuesto';
import { useEstadoOrden } from '@/presentation/hooks/useEstadoOrden';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { hasAnyRole } from '@/presentation/utils/roleVisibility';
import { PresupuestoAplicacionPanel } from '@/presentation/components/budgets/PresupuestoAplicacionPanel';
import { esResultadoIncierto, getApiErrorMessage } from '@/infrastructure/api/errors';
import type { ItemPresupuestoInput } from '@/domain/ports/PresupuestoPort';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import type { Repuesto } from '@/domain/entities/Repuesto';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { Button } from '@/presentation/components/ui/Button';
import { formatMoneyCLP } from '@/presentation/utils/budgetDisplay';
import { BudgetItemRow } from '@/presentation/components/budgets/BudgetItemRow';

interface ItemForm {
    tipo: 'repuesto' | 'mano_de_obra';
    descripcion: string;
    cantidad: string;
    precioUnitario: string;
    repuestoId: string;
}

const emptyItem: ItemForm = {
    tipo: 'mano_de_obra',
    descripcion: '',
    cantidad: '1',
    precioUnitario: '0',
    repuestoId: '',
};

export function BudgetEditor({ administrador }: { administrador: boolean }) {
    const { id } = useParams<{ id: string }>();
    const [presupuesto, setPresupuesto] = useState<Presupuesto | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [repuestos, setRepuestos] = useState<Repuesto[]>([]);
    const [items, setItems] = useState<ItemForm[]>([emptyItem]);
    const [submitting, setSubmitting] = useState(false);
    // Una lectura tardía del servidor no debe pisar lo que la persona ya editó.
    const editado = useRef(false);
    const [incierto, setIncierto] = useState(false);
    const [envioPendiente, setEnvioPendiente] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [aviso, setAviso] = useState<string | null>(null);
    const { estado: estadoOrden, recargar: recargarOrden } = useEstadoOrden(id);
    const usuario = useAuthStore((s) => s.user);
    const hasRole = (rol: 'administrador') => hasAnyRole(usuario, rol);

    const load = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const resumen = await presupuestoService.getByOrder(id);
            const found = resumen ? await presupuestoService.getById(resumen.id) : null;
            setPresupuesto(found);
            if (found?.versiones?.length && !editado.current) {
                const version = found.versiones[found.versiones.length - 1];
                setItems(
                    version.items.map((item) => ({
                        tipo: item.tipo,
                        descripcion: item.descripcion,
                        cantidad: String(item.cantidad),
                        precioUnitario: String(item.precioUnitario),
                        repuestoId: item.repuestoId ?? '',
                    }))
                );
            }
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudo cargar el presupuesto.'));
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => {
        // eslint-disable-next-line react/set-state-in-effect
        void load();
        void (async () => {
            try {
                const response = await repuestoService.getRepuestos({ limite: 200 });
                setRepuestos(response.repuestos);
            } catch {
                setRepuestos([]);
            }
        })();
    }, [load]);

    const addItem = () => { editado.current = true; setItems((prev) => [...prev, { ...emptyItem }]); };

    const updateItem = (index: number, patch: Partial<ItemForm>) => {
        editado.current = true;
        setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
    };

    const removeItem = (index: number) => {
        editado.current = true;
        setItems((prev) => prev.filter((_, i) => i !== index));
    };

    const toInput = (): ItemPresupuestoInput[] =>
        items
            .filter((item) => item.descripcion.trim() !== '')
            .map((item) => ({
                tipo: item.tipo,
                descripcion: item.descripcion.trim(),
                cantidad: Number(item.cantidad),
                precioUnitario: Number(item.precioUnitario),
                repuestoId: item.tipo === 'repuesto' ? item.repuestoId : null,
            }));

    const handleCreate = async () => {
        if (!id) return;
        setSubmitting(true);
        setActionError(null);
        try {
            const created = await presupuestoService.create(id, toInput());
            editado.current = false;
            setPresupuesto(created);
        } catch (err) {
            setActionError(getApiErrorMessage(err, 'No se pudo crear el presupuesto.'));
        } finally {
            setSubmitting(false);
        }
    };

    const handleSaveDraft = async () => {
        if (!presupuesto) return;
        const version = presupuesto.versiones[presupuesto.versiones.length - 1];
        if (!version) return;
        setSubmitting(true);
        setActionError(null);
        try {
            if (version.estado === 'borrador') {
                await presupuestoService.replaceItems(presupuesto.id, version.numero, toInput());
            } else {
                await presupuestoService.createVersion(presupuesto.id, { items: toInput() });
            }
            editado.current = false;
            await load();
        } catch (err) {
            setActionError(getApiErrorMessage(err, 'No se pudo guardar el borrador.'));
        } finally {
            setSubmitting(false);
        }
    };

    const handleSend = async () => {
        if (!presupuesto) return;
        const version = presupuesto.versiones[presupuesto.versiones.length - 1];
        if (!version) return;
        setSubmitting(true);
        setActionError(null);
        setAviso(null);
        try {
            await presupuestoService.replaceItems(presupuesto.id, version.numero, toInput());
            editado.current = false;
            const resultado = await presupuestoService.send(presupuesto.id, version.numero);
            await Promise.all([load(), recargarOrden()]);
            setAviso(resultado?.aplicacionConfirmada
                ? 'Versión enviada al cliente. La orden quedó en "Esperando aprobación de presupuesto".'
                : 'Versión enviada al cliente.');
        } catch (err) {
            if (err instanceof AplicacionPresupuestoPendienteError) {
                // El envío ya está guardado: se conserva la referencia del 503
                // y solo se ofrece el reintento de su aplicación.
                setEnvioPendiente(err.id);
                await Promise.all([load(), recargarOrden()]);
            } else {
                setActionError(getApiErrorMessage(err, 'No se pudo confirmar el envío. Consulte el presupuesto antes de repetir.'));
                if (esResultadoIncierto(err)) { setIncierto(true); await load(); }
            }
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) return <LoadingState message="Cargando presupuesto..." className="p-4 sm:p-6 lg:p-10" />;
    if (error) return <ErrorState className="p-4 sm:p-6 lg:p-10" title="No se pudo cargar el presupuesto" message={error} onRetry={load} />;

    const version = presupuesto?.versiones?.[presupuesto.versiones.length - 1];
    const pendiente = envioPendiente
        ? { tipo: 'envio' as const, id: envioPendiente }
        : aplicacionPendiente(presupuesto, estadoOrden);
    const confirmarAplicacion = async () => {
        setEnvioPendiente(null);
        setActionError(null);
        await Promise.all([load(), recargarOrden()]);
        setAviso('Aplicación confirmada: la orden quedó en "Esperando aprobación de presupuesto".');
    };

    return (
        <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
            <Link to={administrador ? `/admin/ordenes/${id}` : "/mechanic/ordenes"} className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline">
                <ArrowLeft className="w-4 h-4" /> Volver a las órdenes
            </Link>
            <h2 className="text-3xl font-bold mb-2 tracking-tight">Presupuesto de la orden #{id}</h2>
            <p className="text-text-muted text-lg mb-6">{administrador ? 'Revisar los trabajos y precios antes de enviar al cliente' : 'Proponer trabajos y repuestos para revisión del administrador'}</p>

            {incierto && <section className="card p-4 mb-4" aria-label="Envío sin confirmar">
                <p>La respuesta no llegó. Consulte la versión guardada antes de repetir; el servidor podría seguir procesando.</p>
                <Button variant="secondary" onClick={() => void load()}>Comprobar de nuevo</Button>
                <Button variant="secondary" onClick={() => setIncierto(false)}>Ya lo revisé: permitir enviar otra vez</Button>
            </section>}
            {actionError && <div className="card p-4 mb-6 text-status-red" role="alert">{actionError}</div>}
            {aviso && <div className="card p-4 mb-6 text-status-green" role="status">{aviso}</div>}
            {!administrador && (
                <div className="card p-4 mb-6 text-sm" aria-label="Revisión del administrador">
                    <p className="text-text-muted">
                        El Mecánico prepara la propuesta. Un Administrador revisa los precios y la envía al cliente.
                    </p>
                    {pendiente?.tipo === 'envio' && <p className="mt-2">El envío está registrado y su aplicación en la orden está pendiente; la reintenta un Administrador.</p>}
                    {hasRole('administrador') && id && (
                        <Link to={`/admin/ordenes/${id}/presupuesto`} className="inline-block mt-2 text-primary-blue">
                            Revisar y enviar como Administrador
                        </Link>
                    )}
                </div>
            )}

            <div className="card p-6 mb-6 space-y-4">
                {items.map((item, index) => (
                    <div key={index} className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
                        <label className="flex flex-col gap-1 text-sm">
                            <span className="text-text-muted">Tipo</span>
                            <select
                                value={item.tipo}
                                onChange={(e) => updateItem(index, { tipo: e.target.value as 'repuesto' | 'mano_de_obra' })}
                                className="bg-surface border border-border-custom rounded-lg px-3 py-2 text-text-main text-sm"
                            >
                                <option value="mano_de_obra">Mano de obra</option>
                                <option value="repuesto">Repuesto</option>
                            </select>
                        </label>
                        <label className="flex flex-col gap-1 text-sm md:col-span-2">
                            <span className="text-text-muted">Descripción</span>
                            <input
                                value={item.descripcion}
                                onChange={(e) => updateItem(index, { descripcion: e.target.value })}
                                className="bg-surface border border-border-custom rounded-lg px-3 py-2 text-text-main text-sm"
                            />
                        </label>
                        {item.tipo === 'repuesto' && (
                            <label className="flex flex-col gap-1 text-sm">
                                <span className="text-text-muted">Repuesto</span>
                                <select
                                    value={item.repuestoId}
                                    onChange={(e) => updateItem(index, { repuestoId: e.target.value })}
                                    className="bg-surface border border-border-custom rounded-lg px-3 py-2 text-text-main text-sm"
                                >
                                    <option value="">Seleccionar...</option>
                                    {repuestos.map((r) => (
                                        <option key={r.repuestoId} value={r.repuestoId}>{r.nombre}</option>
                                    ))}
                                </select>
                            </label>
                        )}
                        <label className="flex flex-col gap-1 text-sm">
                            <span className="text-text-muted">Cantidad</span>
                            <input
                                type="number"
                                value={item.cantidad}
                                onChange={(e) => updateItem(index, { cantidad: e.target.value })}
                                className="bg-surface border border-border-custom rounded-lg px-3 py-2 text-text-main text-sm"
                            />
                        </label>
                        <label className="flex flex-col gap-1 text-sm">
                            <span className="text-text-muted">Precio unitario</span>
                            <input
                                type="number"
                                value={item.precioUnitario}
                                onChange={(e) => updateItem(index, { precioUnitario: e.target.value })}
                                className="bg-surface border border-border-custom rounded-lg px-3 py-2 text-text-main text-sm"
                            />
                        </label>
                        <div className="flex items-end">
                            <Button variant="danger" onClick={() => removeItem(index)}>Quitar</Button>
                        </div>
                    </div>
                ))}
                <Button variant="secondary" onClick={addItem}>
                    <Plus className="w-4 h-4 mr-2" /> Agregar ítem
                </Button>
            </div>

            {administrador && pendiente?.tipo === 'envio' && (
                <PresupuestoAplicacionPanel tipo="envio" id={pendiente.id} ordenId={id} onConfirmed={confirmarAplicacion} />
            )}
            {administrador && pendiente?.tipo === 'decision' && (
                <div className="card p-4 mb-4 text-sm" role="status">
                    El cliente ya registró su decisión (n° {pendiente.id}) y su aplicación en la orden está pendiente; la reintenta el Cliente desde su presupuesto.
                </div>
            )}
            <div className="flex gap-3">
                {!presupuesto ? (
                    <Button onClick={handleCreate} isLoading={submitting}>Crear presupuesto</Button>
                ) : (
                    <>
                        <Button onClick={handleSaveDraft} isLoading={submitting}>Guardar borrador</Button>
                        {administrador && version?.estado === 'borrador' && !pendiente && !incierto && (
                            <Button onClick={handleSend} isLoading={submitting}>
                                <Send className="w-4 h-4 mr-2" /> Enviar al cliente
                            </Button>
                        )}
                    </>
                )}
            </div>

            {presupuesto && version && (
                <div className="card p-6 mt-6">
                    <h3 className="text-xl font-semibold mb-2">Versión {version.numero} — {version.estado}</h3>
                    <p className="text-text-muted text-sm mb-4">Total: {formatMoneyCLP(version.total)}</p>
                    <div className="flex flex-col gap-3">
                        {version.items.map((item) => (
                            <BudgetItemRow key={item.id} item={item} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}