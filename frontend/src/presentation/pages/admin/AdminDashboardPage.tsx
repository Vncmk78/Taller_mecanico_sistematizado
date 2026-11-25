import {
  Car,
  Clock,
  CheckCircle,
  FileText,
  TrendingUp,
  AlertTriangle,
  Wrench,
  ClipboardList,
  Users,
  Package,
  Truck,
  ListOrdered,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import type { AlertaStock, Movimiento, TipoMovimiento } from '@/domain/entities/Inventario';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { authService } from '@/infrastructure/api/AuthService';
import { orderService } from '@/infrastructure/api/OrderService';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { proveedorService } from '@/infrastructure/api/ProveedorService';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { Alert } from '@/presentation/components/ui/Alert';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { Button } from '@/presentation/components/ui/Button';
import { OrderStatusBadge } from '@/presentation/components/orders/OrderStatusBadge';
import { formatDateTime, orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';

interface CargaMecanico {
  mecanicoId: string;
  nombre: string;
  totalOrdenes: number;
  activas: number;
}

const CARGA_POR_PAGINA = 5;
const LIMITE_PRESUPUESTOS = 200;
const LIMITE_COLA = 5;
const LIMITE_ALERTAS = 3;
const LIMITE_MOVIMIENTOS = 3;

const TIPO_MOVIMIENTO_LABEL: Record<TipoMovimiento, string> = {
  ingreso: 'Ingreso',
  ajuste: 'Ajuste',
  compromiso: 'Compromiso',
  consumo: 'Consumo',
  liberacion: 'Liberación',
};

function esOrdenActiva(orden: Order): boolean {
  return orden.estadoCodigo !== 7 && orden.estadoCodigo !== 8;
}

interface MiniStatProps {
  label: string;
  value: string;
  tone?: 'blue' | 'green' | 'orange' | 'red';
  testId?: string;
}

const miniStatTones: Record<NonNullable<MiniStatProps['tone']>, string> = {
  blue: 'text-primary-blue',
  green: 'text-status-green',
  orange: 'text-status-orange',
  red: 'text-status-red',
};

function MiniStat({ label, value, tone = 'blue', testId }: MiniStatProps) {
  return (
    <div
      data-testid={testId}
      className="rounded-lg border border-border-custom bg-bg-secondary/30 px-3 py-2.5"
    >
      <span className="block text-xs text-text-muted mb-1">{label}</span>
      <strong className={`text-xl font-bold ${miniStatTones[tone]}`}>{value}</strong>
    </div>
  );
}

export function AdminDashboardPage() {
  const [vehiculos, setVehiculos] = useState<Vehicle[]>([]);
  const [totalVehiculos, setTotalVehiculos] = useState<number | null>(null);
  const [totalMecanicos, setTotalMecanicos] = useState<number | null>(null);
  const [totalOrdenes, setTotalOrdenes] = useState<number | null>(null);
  const [ordenesActivas, setOrdenesActivas] = useState<number | null>(null);
  const [esperandoDiagnostico, setEsperandoDiagnostico] = useState<number | null>(null);
  const [listosParaEntrega, setListosParaEntrega] = useState<number | null>(null);
  const [presupuestosPorRevisar, setPresupuestosPorRevisar] = useState<number | null>(null);
  const [colaActiva, setColaActiva] = useState<Order[]>([]);
  const [alertasStock, setAlertasStock] = useState<AlertaStock[]>([]);
  const [totalAlertas, setTotalAlertas] = useState<number | null>(null);
  const [movimientos, setMovimientos] = useState<Movimiento[]>([]);
  const [totalProveedores, setTotalProveedores] = useState<number | null>(null);
  const [totalRepuestos, setTotalRepuestos] = useState<number | null>(null);
  const [repuestosBajoUmbral, setRepuestosBajoUmbral] = useState<number | null>(null);
  const [cargaMecanicos, setCargaMecanicos] = useState<CargaMecanico[]>([]);
  const [cargandoResumen, setCargandoResumen] = useState(true);
  const [errorResumen, setErrorResumen] = useState<string | null>(null);
  const [erroresOperativos, setErroresOperativos] = useState<string[]>([]);
  const [paginaCarga, setPaginaCarga] = useState(1);

  const cargarResumen = async () => {
    setCargandoResumen(true);
    setErrorResumen(null);
    setErroresOperativos([]);

    try {
      const [
        vehiculosRes,
        usuariosRes,
        ordenesRes,
        presupuestosRes,
        alertasRes,
        movimientosRes,
        proveedoresRes,
        repuestosRes,
      ] = await Promise.allSettled([
        vehicleService.getAllVehicles(),
        authService.listarUsuarios(),
        orderService.getOrders(),
        presupuestoService.listar(LIMITE_PRESUPUESTOS),
        inventarioService.listAlertas(),
        inventarioService.listMovimientos({ limite: LIMITE_MOVIMIENTOS }),
        proveedorService.getProveedores(),
        repuestoService.getRepuestos(),
      ]);

      if (vehiculosRes.status === 'fulfilled') {
        setVehiculos(vehiculosRes.value);
        setTotalVehiculos(vehiculosRes.value.length);
      } else {
        setVehiculos([]);
        setTotalVehiculos(null);
      }

      const mecanicos = usuariosRes.status === 'fulfilled'
        ? usuariosRes.value.filter((usuario) => (usuario.roles ?? []).includes('mecanico'))
        : [];
      setTotalMecanicos(usuariosRes.status === 'fulfilled' ? mecanicos.length : null);

      const mapaMecanicos = new Map<string, CargaMecanico>();
      for (const mecanico of mecanicos) {
        mapaMecanicos.set(mecanico.id, {
          mecanicoId: mecanico.id,
          nombre: mecanico.full_name || mecanico.email,
          totalOrdenes: 0,
          activas: 0,
        });
      }

      if (ordenesRes.status === 'fulfilled') {
        const listaOrdenes = ordenesRes.value;
        const activas = listaOrdenes.filter(esOrdenActiva);

        setTotalOrdenes(listaOrdenes.length);
        setOrdenesActivas(activas.length);
        setEsperandoDiagnostico(listaOrdenes.filter((orden) => orden.estadoCodigo === 2).length);
        setListosParaEntrega(listaOrdenes.filter((orden) => orden.estadoCodigo === 6).length);
        setColaActiva(
          [...activas]
            .sort((a, b) => a.estadoCodigo - b.estadoCodigo || a.creadoEn.localeCompare(b.creadoEn))
            .slice(0, LIMITE_COLA)
        );

        for (const orden of listaOrdenes) {
          if (!orden.mecanicoActualId) continue;
          const existente = mapaMecanicos.get(orden.mecanicoActualId);
          if (!existente) {
            mapaMecanicos.set(orden.mecanicoActualId, {
              mecanicoId: orden.mecanicoActualId,
              nombre: orden.mecanicoNombre || `Mecánico ${orden.mecanicoActualId}`,
              totalOrdenes: 1,
              activas: esOrdenActiva(orden) ? 1 : 0,
            });
            continue;
          }
          existente.totalOrdenes += 1;
          if (esOrdenActiva(orden)) existente.activas += 1;
        }

        setCargaMecanicos(
          Array.from(mapaMecanicos.values()).sort((a, b) => {
            if (b.activas !== a.activas) return b.activas - a.activas;
            return b.totalOrdenes - a.totalOrdenes;
          })
        );
        setPaginaCarga(1);
      } else {
        setTotalOrdenes(null);
        setOrdenesActivas(null);
        setEsperandoDiagnostico(null);
        setListosParaEntrega(null);
        setColaActiva([]);
        setCargaMecanicos([]);
        setPaginaCarga(1);
      }

      setPresupuestosPorRevisar(
        presupuestosRes.status === 'fulfilled'
          ? presupuestosRes.value.filter((presupuesto) => presupuesto.estadoUltimaVersion === 'enviada').length
          : null
      );

      if (alertasRes.status === 'fulfilled') {
        setAlertasStock(alertasRes.value.alertas.slice(0, LIMITE_ALERTAS));
        setTotalAlertas(alertasRes.value.total);
      } else {
        setAlertasStock([]);
        setTotalAlertas(null);
      }

      if (movimientosRes.status === 'fulfilled') {
        setMovimientos(movimientosRes.value.movimientos.slice(0, LIMITE_MOVIMIENTOS));
      } else {
        setMovimientos([]);
      }

      setTotalProveedores(proveedoresRes.status === 'fulfilled' ? proveedoresRes.value.total : null);

      if (repuestosRes.status === 'fulfilled') {
        setTotalRepuestos(repuestosRes.value.total);
        setRepuestosBajoUmbral(repuestosRes.value.repuestos.filter((repuesto) => repuesto.bajoUmbral).length);
      } else {
        setTotalRepuestos(null);
        setRepuestosBajoUmbral(null);
      }

      const fallos: string[] = [];
      // Estas tres fuentes sostienen los KPIs principales: si una falla, el
      // panel no puede anunciar "Sistema En línea" aunque el resto responda.
      if (vehiculosRes.status === 'rejected') fallos.push('vehículos');
      if (usuariosRes.status === 'rejected') fallos.push('mecánicos');
      if (ordenesRes.status === 'rejected') fallos.push('órdenes');
      if (presupuestosRes.status === 'rejected') fallos.push('presupuestos');
      if (alertasRes.status === 'rejected') fallos.push('alertas de stock');
      if (movimientosRes.status === 'rejected') fallos.push('movimientos');
      if (proveedoresRes.status === 'rejected') fallos.push('distribuidores');
      if (repuestosRes.status === 'rejected') fallos.push('repuestos');
      setErroresOperativos(fallos);

      if (
        vehiculosRes.status === 'rejected' &&
        usuariosRes.status === 'rejected' &&
        ordenesRes.status === 'rejected'
      ) {
        setErrorResumen(
          getApiErrorMessage(
            vehiculosRes.reason,
            'No se pudo cargar el resumen de órdenes, vehículos y mecánicos.'
          )
        );
      }
    } finally {
      setCargandoResumen(false);
    }
  };

  useEffect(() => {
    void cargarResumen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const formatValor = (valor: number | null) => {
    if (cargandoResumen) return '—';
    if (valor === null) return '—';
    return valor.toLocaleString('es-CL');
  };

  const totalPaginasCarga = Math.max(1, Math.ceil(cargaMecanicos.length / CARGA_POR_PAGINA));
  const paginaCargaSegura = Math.min(paginaCarga, totalPaginasCarga);
  const inicioCarga = (paginaCargaSegura - 1) * CARGA_POR_PAGINA;
  const cargaPaginada = cargaMecanicos.slice(inicioCarga, inicioCarga + CARGA_POR_PAGINA);

  const estadoSistema = cargandoResumen
    ? { label: 'Cargando…', className: 'bg-bg-secondary text-text-muted border-border-custom' }
    : errorResumen
      ? { label: 'Sin conexión', className: 'bg-status-red/20 text-status-red border-status-red/50' }
      : erroresOperativos.length > 0
        ? { label: 'Datos parciales', className: 'bg-status-yellow/20 text-status-yellow border-status-yellow/50' }
        : { label: 'Sistema En línea', className: 'bg-status-green/20 text-status-green border-status-green/50' };

  const stats = [
    {
      label: 'Órdenes totales',
      value: formatValor(totalOrdenes),
      valueColor: 'text-text-main',
      icon: <ClipboardList className="w-6 h-6" />,
      iconColor: 'text-primary-blue',
      iconBg: 'bg-primary-blue/10',
      borderLeft: 'border-l-4 border-l-primary-blue',
      testId: 'kpi-ordenes-totales',
    },
    {
      label: 'Órdenes activas',
      value: formatValor(ordenesActivas),
      valueColor: 'text-primary-blue',
      icon: <TrendingUp className="w-6 h-6" />,
      iconColor: 'text-primary-blue',
      iconBg: 'bg-primary-blue/10',
      borderLeft: 'border-l-4 border-l-primary-blue',
      testId: 'kpi-ordenes-activas',
    },
    {
      label: 'Vehículos registrados',
      value: formatValor(totalVehiculos),
      valueColor: 'text-text-main',
      icon: <Car className="w-6 h-6" />,
      iconColor: 'text-primary-blue',
      iconBg: 'bg-primary-blue/10',
      borderLeft: 'border-l-4 border-l-primary-blue',
      testId: 'kpi-vehiculos',
    },
    {
      label: 'Mecánicos',
      value: formatValor(totalMecanicos),
      valueColor: 'text-status-green',
      icon: <Users className="w-6 h-6" />,
      iconColor: 'text-status-green',
      iconBg: 'bg-status-green/15',
      borderLeft: 'border-l-4 border-l-status-green',
      testId: 'kpi-mecanicos',
    },
    {
      label: 'Esperando diagnóstico',
      value: formatValor(esperandoDiagnostico),
      valueColor: 'text-status-yellow',
      icon: <Clock className="w-6 h-6" />,
      iconColor: 'text-status-yellow',
      iconBg: 'bg-status-yellow/15',
      borderLeft: 'border-l-4 border-l-status-orange',
      testId: 'kpi-diagnostico',
    },
    {
      label: 'Listos para entrega',
      value: formatValor(listosParaEntrega),
      valueColor: 'text-status-green',
      icon: <CheckCircle className="w-6 h-6" />,
      iconColor: 'text-status-green',
      iconBg: 'bg-status-green/15',
      borderLeft: 'border-l-4 border-l-status-green',
      testId: 'kpi-listos',
    },
    {
      label: 'Vehículos en Taller',
      value: formatValor(ordenesActivas),
      valueColor: 'text-primary-blue',
      icon: <Car className="w-6 h-6" />,
      iconColor: 'text-primary-blue',
      iconBg: 'bg-primary-blue/10',
      borderLeft: 'border-l-4 border-l-primary-blue',
      testId: 'kpi-vehiculos-taller',
    },
    {
      label: 'Presupuestos por Revisar',
      value: formatValor(presupuestosPorRevisar),
      valueColor: 'text-status-orange',
      icon: <FileText className="w-6 h-6" />,
      iconColor: 'text-status-orange',
      iconBg: 'bg-status-orange/15',
      borderLeft: 'border-l-4 border-l-status-red',
      testId: 'kpi-presupuestos',
    },
  ];

  const accesos = [
    {
      to: '/admin/ordenes',
      label: 'Gestión de órdenes',
      descripcion: 'Cola, estados y asignaciones',
      icon: <ClipboardList className="w-5 h-5" />,
    },
    {
      to: '/admin/inventario',
      label: 'Inventario',
      descripcion: 'Catálogo y stock de repuestos',
      icon: <Package className="w-5 h-5" />,
    },
    {
      to: '/admin/inventario/alertas',
      label: 'Alertas de stock',
      descripcion: 'Repuestos bajo el umbral',
      icon: <AlertTriangle className="w-5 h-5" />,
    },
    {
      to: '/admin/distribuidores',
      label: 'Distribuidores',
      descripcion: 'Proveedores y contactos',
      icon: <Truck className="w-5 h-5" />,
    },
  ];

  return (
    <div className="animate-fade-in">
      <div className="flex flex-wrap justify-between items-center gap-3 px-4 sm:px-6 lg:px-10 pt-10 pb-5">
        <div>
          <h2 className="text-3xl font-bold mb-2 tracking-tight">
            Panel de Control Global
          </h2>
          <p className="text-text-muted text-lg">
            Resumen operativo del taller
          </p>
        </div>
        <div
          aria-live="polite"
          className={`px-5 py-2.5 rounded-[20px] text-sm font-bold border ${estadoSistema.className}`}
        >
          <span className="text-xs mr-2">●</span> {estadoSistema.label}
        </div>
      </div>

      {errorResumen && (
        <div className="px-4 sm:px-6 lg:px-10 pb-4">
          <ErrorState
            title="No se pudo cargar el resumen del panel"
            message={errorResumen}
            onRetry={() => void cargarResumen()}
            className="py-6"
          />
        </div>
      )}

      {!cargandoResumen && !errorResumen && erroresOperativos.length > 0 && (
        <div className="px-4 sm:px-6 lg:px-10 pb-4">
          <Alert tone="warning">
            No se pudieron cargar {erroresOperativos.join(', ')}. El resto del panel sí está disponible.
          </Alert>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-5 px-4 sm:px-6 lg:px-10 pb-7">
        {stats.map((stat) => (
          <div
            key={stat.label}
            data-testid={stat.testId}
            className={`card flex justify-between items-center p-5 ${stat.borderLeft}`}
          >
            <div>
              <span className="text-text-muted text-sm block mb-2">
                {stat.label}
              </span>
              <h3 className={`text-4xl font-extrabold ${stat.valueColor}`}>
                {stat.value}
              </h3>
            </div>
            <div
              className={`w-14 h-14 rounded-xl flex items-center justify-center text-2xl ${stat.iconColor} ${stat.iconBg}`}
            >
              {stat.icon}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-7 px-4 sm:px-6 lg:px-10 pb-10">
        <div className="flex flex-col gap-7">
          <div className="card flex flex-col p-7">
            <div className="flex justify-between items-center mb-6 border-b border-border-custom pb-4">
              <h3 className="text-xl font-semibold">Carga de mecánicos</h3>
              <p className="text-text-muted text-sm">Órdenes totales / activas</p>
            </div>
            <div className="flex flex-col gap-3.5">
              {cargandoResumen && (
                <div className="flex items-center justify-center py-10">
                  <LoadingState message="Cargando indicadores..." />
                </div>
              )}
              {!cargandoResumen && errorResumen && cargaMecanicos.length === 0 && (
                <ErrorState
                  title="No se pudo cargar la carga de mecánicos"
                  message={errorResumen}
                  onRetry={() => void cargarResumen()}
                />
              )}
              {!cargandoResumen && !errorResumen && cargaMecanicos.length === 0 && (
                <EmptyState
                  icon={Users}
                  title="No hay mecánicos con órdenes asignadas"
                  description="Las órdenes asignadas a mecánicos aparecerán aquí."
                  className="py-6"
                />
              )}
              {!cargandoResumen &&
                cargaPaginada.map((mecanico) => (
                  <div
                    key={mecanico.mecanicoId}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-custom px-4 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-primary-blue/10 flex items-center justify-center text-primary-blue">
                        <Wrench className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-text-main">{mecanico.nombre}</p>
                        <p className="text-xs text-text-muted">ID {mecanico.mecanicoId}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-text-muted">
                        Totales: <strong className="text-text-main">{mecanico.totalOrdenes}</strong>
                      </span>
                      <span className="text-text-muted">
                        Activas: <strong className="text-primary-blue">{mecanico.activas}</strong>
                      </span>
                    </div>
                  </div>
                ))}
              {!cargandoResumen && cargaMecanicos.length > CARGA_POR_PAGINA && (
                <div className="flex items-center justify-between pt-2">
                  <p className="text-sm text-text-muted">
                    Mostrando {inicioCarga + 1} - {Math.min(inicioCarga + CARGA_POR_PAGINA, cargaMecanicos.length)} de{' '}
                    {cargaMecanicos.length} mecánicos
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => setPaginaCarga((p) => Math.max(1, p - 1))}
                      disabled={paginaCargaSegura <= 1}
                      className="inline-flex items-center gap-2"
                    >
                      <ChevronLeft className="w-4 h-4" aria-hidden />
                      Anterior
                    </Button>
                    <span className="text-sm text-text-muted">
                      Página {paginaCargaSegura} de {totalPaginasCarga}
                    </span>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => setPaginaCarga((p) => Math.min(totalPaginasCarga, p + 1))}
                      disabled={paginaCargaSegura >= totalPaginasCarga}
                      className="inline-flex items-center gap-2"
                    >
                      Siguiente
                      <ChevronRight className="w-4 h-4" aria-hidden />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="card flex flex-col p-7">
            <div className="flex flex-wrap justify-between items-center gap-2 mb-6 border-b border-border-custom pb-4">
              <h3 className="text-xl font-semibold">Cola de trabajo activa</h3>
              <Link to="/admin/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                Ver todas las órdenes
              </Link>
            </div>
            {cargandoResumen && (
              <div className="flex items-center justify-center py-10">
                <LoadingState message="Cargando cola de trabajo..." />
              </div>
            )}
            {!cargandoResumen && ordenesActivas === null && (
              <ErrorState
                title="No se pudo cargar la cola de trabajo"
                message="No fue posible consultar las órdenes activas."
                onRetry={() => void cargarResumen()}
              />
            )}
            {!cargandoResumen && ordenesActivas !== null && colaActiva.length === 0 && (
              <EmptyState
                icon={ClipboardList}
                title="No hay órdenes activas"
                description="Las órdenes en curso aparecerán aquí hasta su entrega o cancelación."
                className="py-6"
              />
            )}
            {!cargandoResumen && colaActiva.length > 0 && (
              <div className="flex flex-col gap-3.5">
                {colaActiva.map((orden) => {
                  const patente = orderPatente(orden, vehiculos);
                  return (
                    <Link
                      key={orden.id}
                      to={`/admin/ordenes/${orden.id}`}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-custom px-4 py-3 no-underline hover:border-primary-blue/60 hover:bg-primary-blue/5"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-text-main">Orden #{orden.id}</p>
                        <p className="text-xs text-text-muted truncate">
                          {orderVehicleLabel(orden, vehiculos)}
                          {patente ? ` · ${patente}` : ''}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <OrderStatusBadge estadoCodigo={orden.estadoCodigo} size="sm" />
                        <span className="text-xs text-text-muted">
                          {orden.mecanicoNombre ??
                            (orden.mecanicoActualId ? `Mecánico ${orden.mecanicoActualId}` : 'Sin asignar')}
                        </span>
                      </div>
                    </Link>
                  );
                })}
                {ordenesActivas !== null && ordenesActivas > colaActiva.length && (
                  <p className="text-xs text-text-muted">
                    Mostrando {colaActiva.length} de {ordenesActivas} órdenes activas.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-7">
          <div className="card flex flex-col p-7">
            <div className="flex justify-between items-center mb-5 border-b border-border-custom pb-3">
              <h3 className="text-xl font-semibold">Inventario y proveedores</h3>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-5">
              <MiniStat
                label="Alertas de stock"
                value={formatValor(totalAlertas)}
                tone="orange"
                testId="kpi-alertas"
              />
              <MiniStat
                label="Repuestos"
                value={formatValor(totalRepuestos)}
                testId="kpi-repuestos"
              />
              <MiniStat
                label="Bajo umbral"
                value={formatValor(repuestosBajoUmbral)}
                tone="red"
                testId="kpi-bajo-umbral"
              />
              <MiniStat
                label="Distribuidores"
                value={formatValor(totalProveedores)}
                tone="green"
                testId="kpi-distribuidores"
              />
            </div>

            {cargandoResumen && (
              <div className="flex items-center justify-center py-8">
                <LoadingState message="Cargando inventario..." />
              </div>
            )}

            {!cargandoResumen && erroresOperativos.length === 5 && (
              <ErrorState
                title="No se pudo cargar el inventario"
                message="No fue posible consultar alertas, movimientos, repuestos ni distribuidores."
                onRetry={() => void cargarResumen()}
              />
            )}

            {!cargandoResumen && erroresOperativos.length < 5 && (
              <>
                <div className="mb-5">
                  <div className="flex justify-between items-center gap-2 mb-2">
                    <h4 className="text-sm font-semibold">Alertas recientes</h4>
                    <Link to="/admin/inventario/alertas" className="text-primary-blue text-xs font-medium no-underline hover:underline">
                      Ver alertas
                    </Link>
                  </div>
                  {alertasStock.length === 0 ? (
                    <p className="text-xs text-text-muted">Sin alertas activas.</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {alertasStock.map((alerta) => (
                        <Link
                          key={alerta.repuestoId}
                          to={`/admin/inventario/stock/${alerta.repuestoId}`}
                          className="flex flex-wrap justify-between gap-2 rounded-lg border border-border-custom px-3 py-2 text-xs no-underline hover:border-status-orange/60"
                        >
                          <span className="text-text-main font-medium">{alerta.nombre}</span>
                          <span className="text-status-orange">
                            Stock {alerta.stock} / umbral {alerta.umbralEfectivo}
                          </span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <div className="flex justify-between items-center gap-2 mb-2">
                    <h4 className="flex items-center gap-2 text-sm font-semibold">
                      <ListOrdered className="w-4 h-4" aria-hidden />
                      Últimos movimientos
                    </h4>
                    <Link to="/admin/inventario/movimientos" className="text-primary-blue text-xs font-medium no-underline hover:underline">
                      Ver movimientos
                    </Link>
                  </div>
                  {movimientos.length === 0 ? (
                    <p className="text-xs text-text-muted">Sin movimientos registrados.</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {movimientos.map((movimiento) => (
                        <div
                          key={movimiento.movimientoId}
                          className="flex flex-wrap justify-between gap-2 rounded-lg border border-border-custom px-3 py-2 text-xs"
                        >
                          <span className="text-text-main font-medium">
                            {TIPO_MOVIMIENTO_LABEL[movimiento.tipo]} · Repuesto #{movimiento.repuestoId}
                          </span>
                          <span className="text-text-muted">
                            {formatDateTime(movimiento.fechaHora)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <div className="card flex flex-col p-7">
            <div className="mb-5 border-b border-border-custom pb-3">
              <h3 className="text-xl font-semibold">Accesos rápidos</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {accesos.map((acceso) => (
                <Link
                  key={acceso.to}
                  to={acceso.to}
                  className="flex items-center gap-3 rounded-lg border border-border-custom px-4 py-3 no-underline transition-colors hover:border-primary-blue/60 hover:bg-primary-blue/5"
                >
                  <span className="w-9 h-9 rounded-lg bg-primary-blue/10 text-primary-blue flex items-center justify-center shrink-0">
                    {acceso.icon}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-text-main">{acceso.label}</span>
                    <span className="block text-xs text-text-muted">{acceso.descripcion}</span>
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
