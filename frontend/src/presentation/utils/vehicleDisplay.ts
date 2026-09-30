/**
 * Etiquetas de los datos del vehículo que pueden no venir informados.
 *
 * El contrato de la Gateway declara `anio` y `kilometraje` como opcionales
 * (gateway/contratos/vehiculos.py:122-123) y VehicleService los normaliza a 0
 * cuando llegan en null, así que 0 significa "sin dato" y no "cero real".
 * Estas funciones evitan que la UI imprima "Año: 0" o "Km registrado: 0".
 */

/** Texto para el año del vehículo, o "Sin especificar" si no vino informado. */
export function vehicleYearLabel(year: number): string {
    return year > 0 ? String(year) : 'Sin especificar';
}

/** Kilometraje con separador de miles chileno, o "Sin especificar" si no vino informado. */
export function vehicleMileageLabel(mileage: number): string {
    return mileage > 0 ? `${mileage.toLocaleString('es-CL')} km` : 'Sin especificar';
}
