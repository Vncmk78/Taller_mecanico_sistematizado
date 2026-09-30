import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { mockAssignedVehicleIds, mockVehicles } from '@/infrastructure/mocks/vehicles.mock';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { MechanicVehiclesPage } from '@/presentation/pages/mechanic/MechanicVehiclesPage';

const vehiculosAsignados = mockVehicles.filter((v) => mockAssignedVehicleIds.includes(v.id));
const vehiculoNoAsignado = mockVehicles.find((v) => !mockAssignedVehicleIds.includes(v.id))!;

vi.mock('@/infrastructure/stores/useVehicleStore', () => ({
  useVehicleStore: vi.fn(),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <MechanicVehiclesPage />
    </MemoryRouter>
  );
}

describe('MechanicVehiclesPage: buscador de vehículos asignados', () => {
  beforeEach(() => {
    vi.mocked(useVehicleStore).mockReturnValue({
      vehicles: vehiculosAsignados,
      status: 'success',
      error: null,
      isOffline: false,
      fetchVehicles: vi.fn(),
    });
  });

  it('expone el campo de búsqueda con un nombre accesible', () => {
    renderPage();

    expect(
      screen.getByRole('textbox', { name: 'Buscar por patente, marca o modelo' })
    ).toBeInTheDocument();
  });

  it('filtra los vehículos asignados al escribir en la búsqueda', () => {
    renderPage();

    expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox', { name: 'Buscar por patente, marca o modelo' }), {
      target: { value: 'ABCD-12' },
    });

    expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
    expect(screen.queryByText('Nissan Kicks')).not.toBeInTheDocument();
  });

  it('online muestra lo que devuelve la API sin filtrar en el cliente', () => {
    vi.mocked(useVehicleStore).mockReturnValue({
      vehicles: [vehiculoNoAsignado],
      status: 'success',
      error: null,
      isOffline: false,
      fetchVehicles: vi.fn(),
    });

    renderPage();

    expect(screen.getByText('Hyundai Tucson')).toBeInTheDocument();
  });

  it('offline muestra la caché completa sin volver a filtrar por identidad', () => {
    vi.mocked(useVehicleStore).mockReturnValue({
      vehicles: mockVehicles,
      status: 'success',
      error: null,
      isOffline: true,
      fetchVehicles: vi.fn(),
    });

    renderPage();

    // La caché proviene de GET /vehiculos/asignados, que ya viene filtrada por
    // la Gateway; no se aplica ningún filtro de demo adicional.
    expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
    expect(screen.getByText('Nissan Kicks')).toBeInTheDocument();
    expect(screen.getByText('Hyundai Tucson')).toBeInTheDocument();
  });

  it('muestra el estado vacío cuando no hay vehículos asignados', () => {
    vi.mocked(useVehicleStore).mockReturnValue({
      vehicles: [],
      status: 'success',
      error: null,
      isOffline: false,
      fetchVehicles: vi.fn(),
    });

    renderPage();

    expect(screen.getByText('No tiene vehículos asignados por el momento.')).toBeInTheDocument();
  });

  it('un error del servidor sin caché muestra el estado de error, no el banner offline', () => {
    vi.mocked(useVehicleStore).mockReturnValue({
      vehicles: [],
      status: 'error',
      error: 'El servidor tuvo un problema. Intente más tarde.',
      isOffline: false,
      fetchVehicles: vi.fn(),
    });

    renderPage();

    expect(screen.getByText('No se pudieron cargar los vehículos')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    expect(screen.queryByText(/No se pudo conectar con el servidor/)).not.toBeInTheDocument();
  });

  it('con error del servidor y caché previa avisa pero conserva los vehículos', () => {
    vi.mocked(useVehicleStore).mockReturnValue({
      vehicles: vehiculosAsignados,
      status: 'error',
      error: 'El servidor tuvo un problema. Intente más tarde.',
      isOffline: false,
      fetchVehicles: vi.fn(),
    });

    renderPage();

    expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('El servidor tuvo un problema.');
  });

  it('muestra el identificador real del propietario en lugar de un nombre simulado', () => {
    renderPage();

    expect(
      screen.getByText(`Dueño: Cliente #${vehiculosAsignados[0].clientId}`)
    ).toBeInTheDocument();
  });
});