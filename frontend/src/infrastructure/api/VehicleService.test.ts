import { beforeEach, describe, expect, it, vi } from 'vitest';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import apiClient from '@/infrastructure/config/apiClient';

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
  });

  it('getAssignedVehicles consulta GET /vehiculos/asignados (endpoint pendiente de MS2)', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [vehiculoApi] });

    await vehicleService.getAssignedVehicles();

    expect(apiClient.get).toHaveBeenCalledWith('/vehiculos/asignados');
  });

  it('getVehicleById interpola el id en GET /vehiculos/{id}', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: vehiculoApi });

    const vehicle = await vehicleService.getVehicleById('7');

    expect(apiClient.get).toHaveBeenCalledWith('/vehiculos/7');
    expect(vehicle.id).toBe('7');
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
  });
});