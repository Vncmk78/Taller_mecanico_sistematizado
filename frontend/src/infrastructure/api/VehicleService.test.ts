import { beforeEach, describe, expect, it, vi } from 'vitest';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import apiClient from '@/infrastructure/config/apiClient';
import {
  vehiculoRespuestaReal,
  vehiculoRespuestaSinAnioNiKilometraje,
} from '@/infrastructure/mocks/payloads.reales';

// Fija el contrato HTTP de MS2 consumido por el frontend (ver
// docs/contratos-openapi.md). Cualquier cambio de ruta o de body debe
// coordinarse con el backend y reflejarse aquí.
vi.mock('@/infrastructure/config/apiClient', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

const vehiculoApi = {
  vehiculo_id: 7,
  cliente_id: 4,
  patente: 'KKTT11',
  marca: 'Toyota',
  modelo: 'Yaris',
  anio: 2019,
  kilometraje: 52000,
};

describe('VehicleService: contrato HTTP de MS2 (vehículos)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getMyVehicles consulta GET /vehiculos y traduce al dominio', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [vehiculoApi] });

    const vehicles = await vehicleService.getMyVehicles('cliente-1');

    expect(apiClient.get).toHaveBeenCalledWith('/vehiculos');
    expect(vehicles[0]).toEqual({
      id: '7',
      patent: 'KKTT11',
      brand: 'Toyota',
      model: 'Yaris',
      year: 2019,
      mileage: 52000,
      clientId: 'cliente-1',
    });
  });

  it('getAllVehicles usa la misma ruta GET /vehiculos para el portal Administrador', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [vehiculoApi] });

    const vehicles = await vehicleService.getAllVehicles();

    expect(apiClient.get).toHaveBeenCalledWith('/vehiculos');
    expect(vehicles[0].brand).toBe('Toyota');
    // Sin identidad de sesión, el propietario es el cliente_id real de MS2.
    expect(vehicles[0].clientId).toBe('4');
  });

  it('getAssignedVehicles consulta GET /vehiculos/asignados con el cliente_id real', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [vehiculoApi] });

    const vehicles = await vehicleService.getAssignedVehicles();

    expect(apiClient.get).toHaveBeenCalledWith('/vehiculos/asignados');
    expect(vehicles[0].clientId).toBe('4');
  });

  it('getVehicleById interpola el id en GET /vehiculos/{id}', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: vehiculoApi });

    const vehicle = await vehicleService.getVehicleById('7');

    expect(apiClient.get).toHaveBeenCalledWith('/vehiculos/7');
    expect(vehicle.id).toBe('7');
    expect(vehicle.clientId).toBe('4');
  });

  it('getVehicleById con clientId de sesión conserva la pertenencia del portal Cliente', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: vehiculoApi });

    const vehicle = await vehicleService.getVehicleById('7', '12');

    expect(vehicle.clientId).toBe('12');
  });

  it('createVehicle publica el body en español del contrato MS2', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: vehiculoApi });

    const created = await vehicleService.createVehicle({
      patent: 'KKTT11',
      brand: 'Toyota',
      model: 'Yaris',
      year: 2019,
      mileage: 52000,
    });

    expect(apiClient.post).toHaveBeenCalledWith('/vehiculos', {
      patente: 'KKTT11',
      marca: 'Toyota',
      modelo: 'Yaris',
      anio: 2019,
      kilometraje: 52000,
    });
    expect(created.id).toBe('7');
    expect(created.clientId).toBe('4');
  });
});

// Esta sección no usa payloads inventados: son los cuerpos literales que la
// Gateway declara en gateway/contratos/vehiculos.py, los mismos que
// backend/tests/test_gateway_openapi.py compara con los esquemas reales.
describe('VehicleService: mapeo contra el payload real de la Gateway', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('traduce el ejemplo real del contrato (vehiculo_id 12, AB1234, 2018, 45000 km)', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [vehiculoRespuestaReal] });

    const vehicles = await vehicleService.getAllVehicles();

    expect(vehicles[0]).toEqual({
      id: '12',
      patent: 'AB1234',
      brand: 'Toyota',
      model: 'Corolla',
      year: 2018,
      mileage: 45000,
      clientId: '7',
    });
  });

  it('normaliza a 0 el año y el kilometraje nulos, que en el contrato son opcionales', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [vehiculoRespuestaSinAnioNiKilometraje] });

    const [vehiculo] = await vehicleService.getAllVehicles();

    // El registro de un vehículo no exige año ni kilometraje, así que llegan
    // en null. El dominio los lleva como number y la capa de presentación
    // distingue el 0 de "sin dato" (ver vehicleDisplay.ts).
    expect(vehiculo.year).toBe(0);
    expect(vehiculo.mileage).toBe(0);
    expect(vehiculo.patent).toBe('CD5678');
    expect(vehiculo.clientId).toBe('7');
  });

  it('no inventa datos que el payload real no trae: el id del vehículo es la clave del dominio', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [vehiculoRespuestaReal] });

    const [vehiculo] = await vehicleService.getAllVehicles();

    // El contrato de vehículo no incluye nombre del dueño ni MechanicalData:
    // la UI no puede mostrar esos datos sin inventarlos.
    expect(vehiculo).not.toHaveProperty('ownerName');
  });
});
