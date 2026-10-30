import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { authService } from '@/infrastructure/api/AuthService';
import { orderService } from '@/infrastructure/api/OrderService';
import { AdminDashboardPage } from './AdminDashboardPage';
import type { UserRole } from '@/domain/entities/User';

vi.mock('@/infrastructure/api/VehicleService', () => ({
  vehicleService: {
    getAllVehicles: vi.fn(),
  },
}));

vi.mock('@/infrastructure/api/AuthService', () => ({
  authService: {
    listarUsuarios: vi.fn(),
  },
}));

vi.mock('@/infrastructure/api/OrderService', () => ({
  orderService: {
    getOrders: vi.fn(),
  },
}));

const vehiclesMock = [
  { id: '1', patent: 'ABCD-12', brand: 'Toyota', model: 'Corolla', year: 2020, mileage: 10000, clientId: '10' },
  { id: '2', patent: 'EFGH-34', brand: 'Nissan', model: 'Sentra', year: 2019, mileage: 20000, clientId: '11' },
];

const usuariosMock = [
  { id: '5', email: 'mec1@taller.cl', full_name: 'Carlos Méndez', roles: ['mecanico' as UserRole], is_active: true },
  { id: '6', email: 'mec2@taller.cl', full_name: 'Ana Torres', roles: ['mecanico' as UserRole], is_active: true },
  { id: '1', email: 'admin@taller.cl', full_name: 'Admin', roles: ['administrador' as UserRole], is_active: true },
];

const ordenesMock = [
  {
    id: '100',
    vehicleId: '1',
    ingresoId: 1,
    estadoCodigo: 2,
    mecanicoActualId: '5',
    creadoPorId: '1',
    creadoEn: '2026-10-01T10:00:00',
    actualizadoEn: '2026-10-01T10:00:00',
    mecanicoNombre: 'Carlos Méndez',
  },
  {
    id: '101',
    vehicleId: '2',
    ingresoId: 2,
    estadoCodigo: 5,
    mecanicoActualId: '5',
    creadoPorId: '1',
    creadoEn: '2026-10-01T11:00:00',
    actualizadoEn: '2026-10-01T11:00:00',
    mecanicoNombre: 'Carlos Méndez',
  },
  {
    id: '102',
    vehicleId: '1',
    ingresoId: 3,
    estadoCodigo: 6,
    mecanicoActualId: '6',
    creadoPorId: '1',
    creadoEn: '2026-10-01T12:00:00',
    actualizadoEn: '2026-10-01T12:00:00',
    mecanicoNombre: 'Ana Torres',
  },
  {
    id: '103',
    vehicleId: '2',
    ingresoId: 4,
    estadoCodigo: 7,
    mecanicoActualId: '6',
    creadoPorId: '1',
    creadoEn: '2026-10-01T13:00:00',
    actualizadoEn: '2026-10-01T13:00:00',
    mecanicoNombre: 'Ana Torres',
  },
  {
    id: '104',
    vehicleId: '1',
    ingresoId: 5,
    estadoCodigo: 8,
    mecanicoActualId: null,
    creadoPorId: '1',
    creadoEn: '2026-10-01T14:00:00',
    actualizadoEn: '2026-10-01T14:00:00',
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminDashboardPage />
    </MemoryRouter>
  );
}

describe('AdminDashboardPage: panel administrativo con indicadores', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(vehicleService.getAllVehicles).mockResolvedValue(vehiclesMock);
    vi.mocked(authService.listarUsuarios).mockResolvedValue(usuariosMock);
    vi.mocked(orderService.getOrders).mockResolvedValue(ordenesMock);
  });

  it('muestra los indicadores básicos de órdenes, vehículos y carga de mecánicos', async () => {
    renderPage();

    expect(screen.getByText('Panel de Control Global')).toBeInTheDocument();
    expect(screen.getByText('Resumen operativo del taller')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Órdenes totales')).toBeInTheDocument();
    });

    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('Vehículos registrados')).toBeInTheDocument();
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Mecánicos')).toBeInTheDocument();
    expect(screen.getByText('Esperando diagnóstico')).toBeInTheDocument();
    expect(screen.getByText('Listos para entrega')).toBeInTheDocument();
    expect(screen.getByText('Órdenes activas')).toBeInTheDocument();
    expect(screen.getByText('Vehículos en Taller')).toBeInTheDocument();
  });

  it('muestra la carga de mecánicos con totales y activas', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Carga de mecánicos')).toBeInTheDocument();
    });

    expect(screen.getByText('Carlos Méndez')).toBeInTheDocument();
    expect(screen.getByText('Ana Torres')).toBeInTheDocument();
    expect(screen.getAllByText(/Totales:/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/Activas:/).length).toBeGreaterThanOrEqual(2);
  });

  it('muestra estado de carga mientras se obtienen los indicadores', () => {
    vi.mocked(vehicleService.getAllVehicles).mockReturnValue(new Promise(() => {}));
    vi.mocked(authService.listarUsuarios).mockReturnValue(new Promise(() => {}));
    vi.mocked(orderService.getOrders).mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getByText('Cargando indicadores...')).toBeInTheDocument();
  });

  it('muestra estado de error y permite reintentar', async () => {
    vi.mocked(vehicleService.getAllVehicles).mockRejectedValue(new Error('Error de red'));
    vi.mocked(authService.listarUsuarios).mockRejectedValue(new Error('Error de red'));
    vi.mocked(orderService.getOrders).mockRejectedValue(new Error('Error de red'));

    renderPage();

    expect(
      await screen.findByText('No se pudo cargar el resumen del panel')
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Reintentar/i }).length).toBeGreaterThanOrEqual(1);

    vi.mocked(vehicleService.getAllVehicles).mockResolvedValue(vehiclesMock);
    vi.mocked(authService.listarUsuarios).mockResolvedValue(usuariosMock);
    vi.mocked(orderService.getOrders).mockResolvedValue(ordenesMock);

    fireEvent.click(screen.getAllByRole('button', { name: /Reintentar/i })[0]);

    await waitFor(() => {
      expect(screen.getByText('Panel de Control Global')).toBeInTheDocument();
    });
  });

  it('paginar la carga de mecánicos cuando hay más de 5', async () => {
    const muchosMecanicos = Array.from({ length: 7 }, (_, index) => ({
      id: String(20 + index),
      email: `mec${index}@taller.cl`,
      full_name: `Mecánico ${index + 1}`,
      roles: ['mecanico' as UserRole],
      is_active: true,
    }));
    const muchasOrdenes = Array.from({ length: 7 }, (_, index) => ({
      id: String(200 + index),
      vehicleId: '1',
      ingresoId: index + 1,
      estadoCodigo: 5,
      mecanicoActualId: String(20 + index),
      creadoPorId: '1',
      creadoEn: '2026-10-01T10:00:00',
      actualizadoEn: '2026-10-01T10:00:00',
    }));

    vi.mocked(authService.listarUsuarios).mockResolvedValue(muchosMecanicos);
    vi.mocked(orderService.getOrders).mockResolvedValue(muchasOrdenes);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Mostrando 1 - 5 de 7 mecánicos/i)).toBeInTheDocument();
    }, { timeout: 5000 });

    expect(screen.getByRole('button', { name: /Siguiente/i })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: /Siguiente/i }));

    await waitFor(() => {
      expect(screen.getByText(/Mostrando 6 - 7 de 7 mecánicos/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Anterior/i })).toBeEnabled();
  });
});
