import { Map } from 'lucide-react';
import { ESTADOS_ORDEN } from '@/domain/entities/Order';

interface OrderStateStepperProps {
    /** Código del estado actual de la orden (catálogo fijo 1-8). */
    estadoCodigo: number;
}

/**
 * Representación visual inicial del ciclo de estados de una orden: una línea
 * de tiempo horizontal con las 8 etapas, marcando las alcanzadas, la actual
 * (aria-current) y las futuras; con scroll horizontal en pantallas angostas.
 */
export function OrderStateStepper({ estadoCodigo }: OrderStateStepperProps) {
    const codigos = Object.keys(ESTADOS_ORDEN)
        .map(Number)
        .sort((a, b) => a - b);

    return (
        <section aria-labelledby="order-state-stepper-title" className="glass-card p-6">
            <h3
                id="order-state-stepper-title"
                className="text-xl font-semibold flex items-center gap-2 mb-6"
            >
                <Map className="w-5 h-5 text-text-muted" aria-hidden />
                Ciclo de estados de la orden
            </h3>

            <ol className="flex items-start overflow-x-auto pb-2" aria-label="Ciclo de estados de la orden">
                {codigos.map((codigo, index) => {
                    const reached = codigo <= estadoCodigo;
                    const current = codigo === estadoCodigo;

                    return (
                        <li
                            key={codigo}
                            aria-current={current ? 'step' : undefined}
                            aria-label={`Estado ${codigo}: ${ESTADOS_ORDEN[codigo]}`}
                            className="relative flex flex-col items-center flex-1 min-w-24 px-1 text-center"
                        >
                            <div className="flex items-center w-full">
                                <span
                                    aria-hidden
                                    className={`flex-1 h-1 rounded-full ${
                                        index === 0
                                            ? 'bg-transparent'
                                            : reached
                                              ? 'bg-status-green/60'
                                              : 'bg-border-custom'
                                    }`}
                                />
                                <span
                                    aria-hidden
                                    className={`h-8 w-8 shrink-0 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                                        current
                                            ? 'bg-primary-red text-white ring-4 ring-primary-red/30'
                                            : reached
                                              ? 'bg-status-green/20 text-status-green'
                                              : 'bg-white/10 text-text-muted'
                                    }`}
                                >
                                    {codigo}
                                </span>
                                <span
                                    aria-hidden
                                    className={`flex-1 h-1 rounded-full ${
                                        index === codigos.length - 1
                                            ? 'bg-transparent'
                                            : reached
                                              ? 'bg-status-green/60'
                                              : 'bg-border-custom'
                                    }`}
                                />
                            </div>
                            <span
                                className={`mt-3 text-xs leading-tight whitespace-nowrap ${
                                    current ? 'text-white font-bold' : 'text-text-muted'
                                }`}
                            >
                                {ESTADOS_ORDEN[codigo]}
                            </span>
                        </li>
                    );
                })}
            </ol>
        </section>
    );
}