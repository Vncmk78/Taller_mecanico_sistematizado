/**
 * Los repuestos de la orden solo se pueden consumir mientras sigue en taller:
 * Esperando repuestos (4), En reparación (5) o Listo (6). Después de entregada
 * (7) o cancelada (8) ya no hay trabajo que descontar.
 *
 * Vive fuera del componente para que el archivo de UI solo exporte componentes
 * (regla de Fast Refresh de Oxlint).
 */
export function puedeConsumirRepuestos(estadoCodigo: number): boolean {
    return estadoCodigo >= 4 && estadoCodigo <= 6;
}
