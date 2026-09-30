import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { mockAssignedVehicleIds, mockOwners, mockVehicles } from '@/infrastructure/mocks/vehicles.mock';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { MechanicVehiclesPage } from '@/presentation/pages/mechanic/MechanicVehiclesPage';

const vehiculosAsignados = mockVehicles.filter((v) => mockAssignedVehicleIds.includes(v.id));

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

  it('preserva el nombre del dueño desde el mock cuando hay tarjetas', () => {
    renderPage();

    expect(screen.getByText(`Dueño: ${mockOwners[vehiculosAsignados[0].clientId]?.fullName}`)).toBeInTheDocument();
  });
});