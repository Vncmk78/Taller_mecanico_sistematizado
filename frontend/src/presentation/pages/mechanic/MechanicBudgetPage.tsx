import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Plus, Send } from 'lucide-react';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import type { ItemPresupuestoInput } from '@/domain/ports/PresupuestoPort';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import type { Repuesto } from '@/domain/entities/Repuesto';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { Button } from '@/presentation/components/ui/Button';
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

export function MechanicBudgetPage() {
    const { id } = useParams<{ id: string }>();
    const [presupuesto, setPresupuesto] = useState<Presupuesto | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [repuestos, setRepuestos] = useState<Repuesto[]>([]);
    const [items, setItems] = useState<ItemForm[]>([emptyItem]);
    const [submitting, setSubmitting] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);

    const load = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const found = await presupuestoService.getByOrder(id);
            setPresupuesto(found);
            if (found?.versiones?.length) {
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

    const addItem = () => setItems((prev) => [...prev, { ...emptyItem }]);

    const updateItem = (index: number, patch: Partial<ItemForm>) => {
        setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
    };

    const removeItem = (index: number) => {
        setItems((prev) => prev.filter((_, i) => i !== index));
    };

    const toInput = (): ItemPresupuestoInput[] =>
        items
            .filter((item) => item.descripcion.trim() !== '')
            .map((item) => ({
                tipo: item.tipo,
                descripcion: item.descripcion.trim(),
                cantidad: Number(item.cantidad) || 1,
                precioUnitario: Number(item.precioUnitario) || 0,
                repuestoId: item.tipo === 'repuesto' ? item.repuestoId : null,
            }));

    const handleCreate = async () => {
        if (!id) return;
        setSubmitting(true);
        setActionError(null);
        try {
            const created = await presupuestoService.create(id, toInput());
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
        try {
            await presupuestoService.send(presupuesto.id, version.numero);
            await load();
        } catch (err) {
            setActionError(getApiErrorMessage(err, 'No se pudo enviar el presupuesto.'));
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) return <LoadingState message="Cargando presupuesto..." className="p-4 sm:p-6 lg:p-10" />;
    if (error) return <ErrorState className="p-4 sm:p-6 lg:p-10" title="No se pudo cargar el presupuesto" message={error} onRetry={load} />;

    const version = presupuesto?.versiones?.[presupuesto.versiones.length - 1];

    return (
        <div className="p-4 sm:p-6 lg:p-10 animate-fade-in">
            <Link to="/mechanic/ordenes" className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline">
                <ArrowLeft className="w-4 h-4" /> Volver a mis órdenes
            </Link>
            <h2 className="text-3xl font-bold mb-2 tracking-tight">Presupuesto de la orden #{id}</h2>
            <p className="text-text-muted text-lg mb-6">Armar y enviar el presupuesto al cliente</p>

            {actionError && <div className="card p-4 mb-6 text-status-red">{actionError}</div>}

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

            <div className="flex gap-3">
                {!presupuesto ? (
                    <Button onClick={handleCreate} isLoading={submitting}>Crear presupuesto</Button>
                ) : (
                    <>
                        <Button onClick={handleSaveDraft} isLoading={submitting}>Guardar borrador</Button>
                        {version?.estado === 'borrador' && (
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
                    <p className="text-text-muted text-sm mb-4">Total: {version.total}</p>
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