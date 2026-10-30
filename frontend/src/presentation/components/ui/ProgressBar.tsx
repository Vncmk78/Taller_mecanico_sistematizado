interface ProgressBarProps {
    /** Porcentaje completado (0-100); se recorta a ese rango. */
    value: number;
    /** Etiqueta accesible que describe qué se está cargando. */
    label?: string;
    className?: string;
}

/** Barra de progreso accesible (se anuncia con role="progressbar"). */
export function ProgressBar({ value, label = 'Progreso', className = '' }: ProgressBarProps) {
    const porcentaje = Math.min(100, Math.max(0, Math.round(value)));

    return (
        <div
            role="progressbar"
            aria-label={label}
            aria-valuenow={porcentaje}
            aria-valuemin={0}
            aria-valuemax={100}
            className={`h-2.5 w-full overflow-hidden rounded-full bg-bg-secondary ${className}`}
        >
            <div
                className="h-full rounded-full bg-primary-blue transition-[width] duration-200"
                style={{ width: `${porcentaje}%` }}
            />
        </div>
    );
}