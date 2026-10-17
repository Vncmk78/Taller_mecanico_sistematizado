import { describe, expect, it } from 'vitest';
import { vehicleMileageLabel, vehicleYearLabel } from './vehicleDisplay';

// El contrato de la Gateway declara `anio` y `kilometraje` como opcionales y
// VehicleService los normaliza a 0 cuando llegan en null, así que 0 significa
// "sin dato". Estas etiquetas evitan que la tarjeta y la ficha del vehículo
// impriman "Año: 0" o "Km registrado: 0".
describe('vehicleDisplay: etiquetas de datos que pueden no venir', () => {
    it('muestra el año cuando el vehículo lo tiene informado', () => {
        expect(vehicleYearLabel(2018)).toBe('2018');
    });

    it('omite el año cuando llegó en null (0 significa sin dato)', () => {
        expect(vehicleYearLabel(0)).toBe('Sin especificar');
    });

    it('muestra el kilometraje con separador de miles cuando está informado', () => {
        expect(vehicleMileageLabel(45000)).toBe('45.000 km');
    });

    it('omite el kilometraje cuando llegó en null', () => {
        expect(vehicleMileageLabel(0)).toBe('Sin especificar');
    });

    it('no confunde un kilometraje de 1 km con la ausencia de dato', () => {
        // El límite es "> 0": un vehículo recién ingresado sí puede tener 1 km.
        expect(vehicleMileageLabel(1)).toBe('1 km');
        expect(vehicleYearLabel(1)).toBe('1');
    });
});
