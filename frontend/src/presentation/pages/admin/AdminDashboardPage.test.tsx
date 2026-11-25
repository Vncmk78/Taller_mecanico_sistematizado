import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { PaginaAlertas, PaginaMovimientos } from '@/domain/entities/Inventario';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import type { PaginaProveedores } from '@/domain/entities/Proveedor';
import type { PaginaRepuestos } from '@/domain/entities/Repuesto';
import type { UserRole } from '@/domain/entities/User';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { authService } from '@/infrastructure/api/AuthService';
import { orderService } from '@/infrastructure/api/OrderService';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { proveedorService } from '@/infrastructure/api/ProveedorService';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { AdminDashboardPage } from './AdminDashboardPage';

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

vi.mock('@/infrastructure/api/PresupuestoService', () => ({
  presupuestoService: {
    listar: vi.fn(),
  },
}));

vi.mock('@/infrastructure/api/InventarioService', () => ({
  inventarioService: {
    listAlertas: vi.fn(),
    listMovimientos: vi.fn(),
  },
}));

vi.mock('@/infrastructure/api/ProveedorService', () => ({
  proveedorService: {
    getProveedores: vi.fn(),
  },
}));

vi.mock('@/infrastructure/api/RepuestoService', () => ({
  repuestoService: {
    getRepuestos: vi.fn(),
  },
}));

const vehiclesMock: Vehicle[] = [
  { id: '1', patent: 'ABCD-12', brand: 'Toyota', model: 'Corolla', year: 2020, mileage: 10000, clientId: '10' },
  { id: '2', patent: 'EFGH-34', brand: 'Nissan', model: 'Sentra', year: 2019, mileage: 20000, clientId: '11' },
];

const usuariosMock = [
  { id: '5', email: 'mec1@taller.cl', full_name: 'Carlos Méndez', roles: ['mecanico' as UserRole], is_active: true },
  { id: '6', email: 'mec2@taller.cl', full_name: 'Ana Torres', roles: ['mecanico' as UserRole], is_active: true },
  { id: '1', email: 'admin@taller.cl', full_name: 'Admin', roles: ['administrador' as UserRole], is_active: true },
];

const ordenesMock: Order[] = [
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
    patente: 'ABCD-12',
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
    patente: 'EFGH-34',
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
    patente: 'ABCD-12',
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
    patente: 'EFGH-34',
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
    patente: 'ABCD-12',
  },
];

const presupuestosMock: Presupuesto[] = [
  {
    id: '501',
    orderId: '100',
    creadoEn: '2026-10-01T10:30:00',
    cantidadVersiones: 1,
    ultimaVersion: 1,
    estadoUltimaVersion: 'enviada',
    totalUltimaVersion: 150000,
    versionVigente: null,
    versiones: [],
  },
  {
    id: '502',
    orderId: '101',
    creadoEn: '2026-10-01T11:30:00',
    cantidadVersiones: 1,
    ultimaVersion: 1,
    estadoUltimaVersion: 'aprobada',
    totalUltimaVersion: 90000,
    versionVigente: 1,
    versiones: [],
  },
  {
    id: '503',
    orderId: '102',
    creadoEn: '2026-10-01T12:30:00',
    cantidadVersiones: 1,
    ultimaVersion: 1,
    estadoUltimaVersion: 'borrador',
    totalUltimaVersion: 45000,
    versionVigente: null,
    versiones: [],
  },
];

const alertasMock: PaginaAlertas = {
  umbralGeneral: 5,
  total: 2,
  alertas: [
    {
      repuestoId: 12,
      nombre: 'Kit Pastillas de Freno',
      proveedorNombre: 'Distribuidor Oficial',
      stock: 2,
      umbralEfectivo: 5,
      faltan: 3,
    },
    {
      repuestoId: 13,
      nombre: 'Filtro de Aceite',
      proveedorNombre: 'Distribuidor Genérico',
      stock: 1,
      umbralEfectivo: 4,
      faltan: 3,
    },
  ],
};

const movimientosMock: PaginaMovimientos = {
  total: 2,
  desde: 0,
  limite: 3,
  movimientos: [
    {
      movimientoId: 900,
      claveOperacion: 'ingreso-900',
      repuestoId: 12,
      tipo: 'ingreso',
      cantidad: 10,
      ordenId: null,
      proveedorId: 31,
      fechaHora: '2026-10-02T09:00:00',
      registradoPorId: 1,
    },
    {
      movimientoId: 901,
      claveOperacion: 'consumo-901',
      repuestoId: 13,
      tipo: 'consumo',
      cantidad: 2,
      ordenId: 101,
      proveedorId: null,
      fechaHora: '2026-10-02T10:30:00',
      registradoPorId: 5,
    },
  ],
};

const proveedoresMock: PaginaProveedores = {
  total: 4,
  desde: 0,
  limite: 50,
  proveedores: Array.from({ length: 4 }, (_, index) => ({
    proveedorId: 31 + index,
    nombre: `Distribuidor ${index + 1}`,
    contacto: `contacto${index + 1}@taller.cl`,
    tipoDistribuidor: index === 0 ? 'oficial' : 'generico',
    cantidadRepuestos: 2,
  })),
};

const repuestosMock: PaginaRepuestos = {
  total: 6,
  desde: 0,
  limite: 50,
  umbralGeneral: 5,
  repuestos: Array.from({ length: 6 }, (_, index) => ({
    repuestoId: 12 + index,
    nombre: `Repuesto ${index + 1}`,
    proveedorId: 31,
    proveedorNombre: 'Distribuidor Oficial',
    proveedorTipoDistribuidor: 'oficial',
    stock: index < 2 ? 2 : 10,
    umbralParticular: null,
    umbralEfectivo: 5,
    bajoUmbral: index < 2,
  })),
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminDashboardPage />
    </MemoryRouter>
  );
}

function kpiValor(testId: string): string {
  return within(screen.getByTestId(testId)).getByText(/^\d+$/).textContent ?? '';
}

describe('AdminDashboardPage: panel administrativo con indicadores reales', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(vehicleService.getAllVehicles).mockResolvedValue(vehiclesMock);
    vi.mocked(authService.listarUsuarios).mockResolvedValue(usuariosMock);
    vi.mocked(orderService.getOrders).mockResolvedValue(ordenesMock);
    vi.mocked(presupuestoService.listar).mockResolvedValue(presupuestosMock);
    vi.mocked(inventarioService.listAlertas).mockResolvedValue(alertasMock);
    vi.mocked(inventarioService.listMovimientos).mockResolvedValue(movimientosMock);
    vi.mocked(proveedorService.getProveedores).mockResolvedValue(proveedoresMock);
    vi.mocked(repuestoService.getRepuestos).mockResolvedValue(repuestosMock);
  });

  it('muestra los indicadores básicos desde la API y sin textos de relleno', async () => {
    renderPage();

    expect(screen.getByText('Panel de Control Global')).toBeInTheDocument();
    expect(screen.getByText('Resumen operativo del taller')).toBeInTheDocument();

    await waitFor(() => {
      expect(kpiValor('kpi-ordenes-totales')).toBe('5');
    });

    expect(kpiValor('kpi-ordenes-activas')).toBe('3');
    expect(kpiValor('kpi-vehiculos')).toBe('2');
    expect(kpiValor('kpi-mecanicos')).toBe('2');
    expect(kpiValor('kpi-diagnostico')).toBe('1');
    expect(kpiValor('kpi-listos')).toBe('1');
    expect(kpiValor('kpi-vehiculos-taller')).toBe('3');
    expect(screen.getByText('Órdenes totales')).toBeInTheDocument();
    expect(screen.getByText('Vehículos registrados')).toBeInTheDocument();
    expect(screen.getByText('Mecánicos')).toBeInTheDocument();
    expect(screen.getAllByText('Esperando diagnóstico').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Listos para entrega')).toBeInTheDocument();
    expect(screen.getByText('Órdenes activas')).toBeInTheDocument();
    expect(screen.getByText('Vehículos en Taller')).toBeInTheDocument();
    expect(screen.queryByText('—')).not.toBeInTheDocument();
    expect(screen.queryByText('Actividad Reciente')).not.toBeInTheDocument();
    expect(screen.queryByText(/Pronto se mostrará el historial/)).not.toBeInTheDocument();
  });

  it('muestra la carga de mecánicos con totales y activas', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Carga de mecánicos')).toBeInTheDocument();
    });

    expect(screen.getAllByText('Carlos Méndez').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Ana Torres').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Totales:/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/Activas:/).length).toBeGreaterThanOrEqual(2);
  });

  it('muestra la cola activa con enlace al detalle y excluye entregadas y canceladas', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Cola de trabajo activa')).toBeInTheDocument();
    });

    const primera = screen.getByRole('link', { name: /Orden #100/i });
    expect(primera).toHaveAttribute('href', '/admin/ordenes/100');
    expect(primera).toHaveTextContent('Esperando diagnóstico');
    expect(primera).toHaveTextContent('ABCD-12');

    expect(screen.getByRole('link', { name: /Orden #101/i })).toHaveAttribute('href', '/admin/ordenes/101');
    expect(screen.getByRole('link', { name: /Orden #102/i })).toHaveAttribute('href', '/admin/ordenes/102');
    expect(screen.queryByRole('link', { name: /Orden #103/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Orden #104/i })).not.toBeInTheDocument();
  });

  it('cuenta los presupuestos enviados desde GET /presupuestos', async () => {
    renderPage();

    await waitFor(() => {
      expect(kpiValor('kpi-presupuestos')).toBe('1');
    });

    expect(presupuestoService.listar).toHaveBeenCalledWith(200);
    expect(screen.getByText('Presupuestos por Revisar')).toBeInTheDocument();
    expect(screen.queryByText('—')).not.toBeInTheDocument();
  });

  it('muestra el panel operativo de inventario, proveedores y accesos rápidos', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Inventario y proveedores')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(kpiValor('kpi-alertas')).toBe('2');
    });

    expect(kpiValor('kpi-repuestos')).toBe('6');
    expect(kpiValor('kpi-bajo-umbral')).toBe('2');
    expect(kpiValor('kpi-distribuidores')).toBe('4');
    expect(screen.getByText('Kit Pastillas de Freno')).toBeInTheDocument();
    expect(screen.getByText(/Consumo · Repuesto #13/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Ver alertas/i })).toHaveAttribute('href', '/admin/inventario/alertas');
    expect(screen.getByRole('link', { name: /Ver movimientos/i })).toHaveAttribute('href', '/admin/inventario/movimientos');
    expect(screen.getByRole('link', { name: /Gestión de órdenes/i })).toHaveAttribute('href', '/admin/ordenes');
    expect(screen.getByRole('link', { name: /^InventarioCatálogo/ })).toHaveAttribute('href', '/admin/inventario');
    expect(screen.getAllByRole('link', { name: /Alertas de stockRepuestos bajo el umbral/i })[0]).toHaveAttribute('href', '/admin/inventario/alertas');
    expect(screen.getByRole('link', { name: /DistribuidoresProveedores y contactos/i })).toHaveAttribute('href', '/admin/distribuidores');
  });

  it('degrada parcialmente si falla solo el listado de presupuestos', async () => {
    vi.mocked(presupuestoService.listar).mockRejectedValue(new Error('MS3 no disponible'));

    renderPage();

    await waitFor(() => {
      expect(kpiValor('kpi-ordenes-totales')).toBe('5');
    });

    expect(within(screen.getByTestId('kpi-presupuestos')).getByText('—')).toBeInTheDocument();
    expect(screen.getByText(/No se pudieron cargar presupuestos/)).toBeInTheDocument();
    expect(screen.getByText('Datos parciales')).toBeInTheDocument();
    expect(kpiValor('kpi-alertas')).toBe('2');
    expect(screen.queryByText('No se pudo cargar el resumen del panel')).not.toBeInTheDocument();
  });

  it('muestra estado de carga mientras se obtienen los indicadores', () => {
    vi.mocked(vehicleService.getAllVehicles).mockReturnValue(new Promise(() => {}));
    vi.mocked(authService.listarUsuarios).mockReturnValue(new Promise(() => {}));
    vi.mocked(orderService.getOrders).mockReturnValue(new Promise(() => {}));
    vi.mocked(presupuestoService.listar).mockReturnValue(new Promise(() => {}));
    vi.mocked(inventarioService.listAlertas).mockReturnValue(new Promise(() => {}));
    vi.mocked(inventarioService.listMovimientos).mockReturnValue(new Promise(() => {}));
    vi.mocked(proveedorService.getProveedores).mockReturnValue(new Promise(() => {}));
    vi.mocked(repuestoService.getRepuestos).mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getByText('Cargando indicadores...')).toBeInTheDocument();
  });

  it('muestra estado de error y permite reintentar', async () => {
    vi.mocked(vehicleService.getAllVehicles).mockRejectedValue(new Error('Error de red'));
    vi.mocked(authService.listarUsuarios).mockRejectedValue(new Error('Error de red'));
    vi.mocked(orderService.getOrders).mockRejectedValue(new Error('Error de red'));
    vi.mocked(presupuestoService.listar).mockRejectedValue(new Error('Error de red'));
    vi.mocked(inventarioService.listAlertas).mockRejectedValue(new Error('Error de red'));
    vi.mocked(inventarioService.listMovimientos).mockRejectedValue(new Error('Error de red'));
    vi.mocked(proveedorService.getProveedores).mockRejectedValue(new Error('Error de red'));
    vi.mocked(repuestoService.getRepuestos).mockRejectedValue(new Error('Error de red'));

    renderPage();

    expect(
      await screen.findByText('No se pudo cargar el resumen del panel')
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Reintentar/i }).length).toBeGreaterThanOrEqual(1);

    vi.mocked(vehicleService.getAllVehicles).mockResolvedValue(vehiclesMock);
    vi.mocked(authService.listarUsuarios).mockResolvedValue(usuariosMock);
    vi.mocked(orderService.getOrders).mockResolvedValue(ordenesMock);
    vi.mocked(presupuestoService.listar).mockResolvedValue(presupuestosMock);
    vi.mocked(inventarioService.listAlertas).mockResolvedValue(alertasMock);
    vi.mocked(inventarioService.listMovimientos).mockResolvedValue(movimientosMock);
    vi.mocked(proveedorService.getProveedores).mockResolvedValue(proveedoresMock);
    vi.mocked(repuestoService.getRepuestos).mockResolvedValue(repuestosMock);

    fireEvent.click(screen.getAllByRole('button', { name: /Reintentar/i })[0]);

    await waitFor(() => {
      expect(kpiValor('kpi-ordenes-totales')).toBe('5');
    });
  });

  it('pagina la carga de mecánicos cuando hay más de 5', { timeout: 15000 }, async () => {
    const muchosMecanicos = Array.from({ length: 7 }, (_, index) => ({
      id: String(20 + index),
      email: `mec${index}@taller.cl`,
      full_name: `Mecánico ${index + 1}`,
      roles: ['mecanico' as UserRole],
      is_active: true,
    }));
    const muchasOrdenes: Order[] = Array.from({ length: 7 }, (_, index) => ({
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
