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
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { authService } from '@/infrastructure/api/AuthService';
import { orderService } from '@/infrastructure/api/OrderService';
import { getApiErrorMessage } from '@/infrastructure/api/errors';

interface CargaMecanico {
  mecanicoId: string;
  nombre: string;
  totalOrdenes: number;
  activas: number;
}

export function AdminDashboardPage() {
  const [totalVehiculos, setTotalVehiculos] = useState<number | null>(null);
  const [totalMecanicos, setTotalMecanicos] = useState<number | null>(null);
  const [totalOrdenes, setTotalOrdenes] = useState<number | null>(null);
  const [ordenesActivas, setOrdenesActivas] = useState<number | null>(null);
  const [esperandoDiagnostico, setEsperandoDiagnostico] = useState<number | null>(null);
  const [listosParaEntrega, setListosParaEntrega] = useState<number | null>(null);
  const [cargaMecanicos, setCargaMecanicos] = useState<CargaMecanico[]>([]);
  const [cargandoResumen, setCargandoResumen] = useState(true);
  const [errorResumen, setErrorResumen] = useState<string | null>(null);

  useEffect(() => {
    let activo = true;

    const cargarResumen = async () => {
      setCargandoResumen(true);
      setErrorResumen(null);
      try {
        const [vehiculos, usuarios, ordenes] = await Promise.allSettled([
          vehicleService.getAllVehicles(),
          authService.listarUsuarios(),
          orderService.getOrders(),
        ]);

        if (!activo) return;

        if (vehiculos.status === 'fulfilled') {
          setTotalVehiculos(vehiculos.value.length);
        } else {
          setTotalVehiculos(null);
        }

        if (usuarios.status === 'fulfilled') {
          const listaUsuarios = usuarios.value;
          const mecanicos = listaUsuarios.filter((usuario) =>
            (usuario.roles ?? []).includes('mecanico')
          );
          setTotalMecanicos(mecanicos.length);

          if (ordenes.status === 'fulfilled') {
            const listaOrdenes = ordenes.value;
            setTotalOrdenes(listaOrdenes.length);

            const activas = listaOrdenes.filter((orden) => orden.estadoCodigo !== 7 && orden.estadoCodigo !== 8).length;
            setOrdenesActivas(activas);
            setEsperandoDiagnostico(listaOrdenes.filter((orden) => orden.estadoCodigo === 2).length);
            setListosParaEntrega(listaOrdenes.filter((orden) => orden.estadoCodigo === 6).length);

            const mapaMecanicos = new Map<string, CargaMecanico>();
            for (const mecanico of mecanicos) {
              mapaMecanicos.set(mecanico.id, {
                mecanicoId: mecanico.id,
                nombre: mecanico.full_name || mecanico.email,
                totalOrdenes: 0,
                activas: 0,
              });
            }

            for (const orden of listaOrdenes) {
              if (!orden.mecanicoActualId) continue;
              const existente = mapaMecanicos.get(orden.mecanicoActualId);
              if (!existente) {
                mapaMecanicos.set(orden.mecanicoActualId, {
                  mecanicoId: orden.mecanicoActualId,
                  nombre: orden.mecanicoNombre || `Mecánico ${orden.mecanicoActualId}`,
                  totalOrdenes: 1,
                  activas: orden.estadoCodigo !== 7 && orden.estadoCodigo !== 8 ? 1 : 0,
                });
                continue;
              }
              existente.totalOrdenes += 1;
              if (orden.estadoCodigo !== 7 && orden.estadoCodigo !== 8) {
                existente.activas += 1;
              }
            }

            const cargaOrdenada = Array.from(mapaMecanicos.values()).sort((a, b) => {
              if (b.activas !== a.activas) return b.activas - a.activas;
              return b.totalOrdenes - a.totalOrdenes;
            });
            setCargaMecanicos(cargaOrdenada);
          } else {
            setTotalOrdenes(null);
            setOrdenesActivas(null);
            setEsperandoDiagnostico(null);
            setListosParaEntrega(null);
            setCargaMecanicos([]);
          }
        } else {
          setTotalMecanicos(null);
          setCargaMecanicos([]);
          if (ordenes.status === 'fulfilled') {
            const listaOrdenes = ordenes.value;
            setTotalOrdenes(listaOrdenes.length);
            const activas = listaOrdenes.filter((orden) => orden.estadoCodigo !== 7 && orden.estadoCodigo !== 8).length;
            setOrdenesActivas(activas);
            setEsperandoDiagnostico(listaOrdenes.filter((orden) => orden.estadoCodigo === 2).length);
            setListosParaEntrega(listaOrdenes.filter((orden) => orden.estadoCodigo === 6).length);
          } else {
            setTotalOrdenes(null);
            setOrdenesActivas(null);
            setEsperandoDiagnostico(null);
            setListosParaEntrega(null);
          }
        }

        if (
          vehiculos.status === 'rejected' &&
          usuarios.status === 'rejected' &&
          ordenes.status === 'rejected'
        ) {
          setErrorResumen(
            getApiErrorMessage(
              vehiculos.reason,
              'No se pudo cargar el resumen de órdenes, vehículos y mecánicos.'
            )
          );
        }
      } finally {
        if (activo) {
          setCargandoResumen(false);
        }
      }
    };

    void cargarResumen();

    return () => {
      activo = false;
    };
  }, []);

  const formatValor = (valor: number | null) => {
    if (cargandoResumen) return '—';
    if (valor === null) return '—';
    return valor.toLocaleString('es-CL');
  };

  const stats = [
    {
      label: 'Órdenes totales',
      value: formatValor(totalOrdenes),
      valueColor: 'text-text-main',
      icon: <ClipboardList className="w-6 h-6" />,
      iconColor: 'text-primary-blue',
      iconBg: 'bg-primary-blue/10',
      borderLeft: 'border-l-4 border-l-primary-blue',
    },
    {
      label: 'Órdenes activas',
      value: formatValor(ordenesActivas),
      valueColor: 'text-primary-blue',
      icon: <TrendingUp className="w-6 h-6" />,
      iconColor: 'text-primary-blue',
      iconBg: 'bg-primary-blue/10',
      borderLeft: 'border-l-4 border-l-primary-blue',
    },
    {
      label: 'Vehículos registrados',
      value: formatValor(totalVehiculos),
      valueColor: 'text-text-main',
      icon: <Car className="w-6 h-6" />,
      iconColor: 'text-primary-blue',
      iconBg: 'bg-primary-blue/10',
      borderLeft: 'border-l-4 border-l-primary-blue',
    },
    {
      label: 'Mecánicos',
      value: formatValor(totalMecanicos),
      valueColor: 'text-status-green',
      icon: <Users className="w-6 h-6" />,
      iconColor: 'text-status-green',
      iconBg: 'bg-status-green/15',
      borderLeft: 'border-l-4 border-l-status-green',
    },
    {
      label: 'Esperando diagnóstico',
      value: formatValor(esperandoDiagnostico),
      valueColor: 'text-status-yellow',
      icon: <Clock className="w-6 h-6" />,
      iconColor: 'text-status-yellow',
      iconBg: 'bg-status-yellow/15',
      borderLeft: 'border-l-4 border-l-status-orange',
    },
    {
      label: 'Listos para entrega',
      value: formatValor(listosParaEntrega),
      valueColor: 'text-status-green',
      icon: <CheckCircle className="w-6 h-6" />,
      iconColor: 'text-status-green',
      iconBg: 'bg-status-green/15',
      borderLeft: 'border-l-4 border-l-status-green',
    },
    {
      label: 'Vehículos en Taller',
      value: formatValor(ordenesActivas),
      valueColor: 'text-primary-blue',
      icon: <Car className="w-6 h-6" />,
      iconColor: 'text-primary-blue',
      iconBg: 'bg-primary-blue/10',
      borderLeft: 'border-l-4 border-l-primary-blue',
    },
    {
      label: 'Presupuestos por Revisar',
      value: '—',
      valueColor: 'text-status-orange',
      icon: <FileText className="w-6 h-6" />,
      iconColor: 'text-status-orange',
      iconBg: 'bg-status-orange/15',
      borderLeft: 'border-l-4 border-l-status-red',
    },
  ];

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center px-10 pt-10 pb-5">
        <div>
          <h2 className="text-3xl font-bold mb-2 tracking-tight">
            Panel de Control Global
          </h2>
          <p className="text-text-muted text-lg">
            Resumen operativo del taller
          </p>
        </div>
        <div className="bg-status-green/20 px-5 py-2.5 rounded-[20px] text-status-green text-sm font-bold border border-status-green/50">
          <span className="text-xs mr-2">●</span> Sistema En línea
        </div>
      </div>

      {errorResumen && (
        <div className="px-10 pb-4">
          <div className="rounded-lg border border-status-red/40 bg-status-red/10 px-4 py-2 text-sm text-status-red">
            {errorResumen}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-5 px-10 pb-7">
        {stats.map((stat) => (
          <div
            key={stat.label}
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

      <div className="grid grid-cols-[2fr_1fr] gap-7 px-10 pb-10">
        <div className="card flex flex-col p-7">
          <div className="flex justify-between items-center mb-6 border-b border-border-custom pb-4">
            <h3 className="text-xl font-semibold">Carga de mecánicos</h3>
            <p className="text-text-muted text-sm">Órdenes totales / activas</p>
          </div>
          <div className="flex flex-col gap-3.5">
            {cargandoResumen && (
              <p className="text-text-muted text-center py-10">Cargando indicadores...</p>
            )}
            {!cargandoResumen && cargaMecanicos.length === 0 && (
              <p className="text-text-muted text-center py-10">
                No hay mecánicos con órdenes asignadas.
              </p>
            )}
            {!cargandoResumen &&
              cargaMecanicos.map((mecanico) => (
                <div
                  key={mecanico.mecanicoId}
                  className="flex items-center justify-between rounded-lg border border-border-custom px-4 py-3"
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
          </div>
        </div>

        <div className="flex flex-col gap-7">
          <div className="card">
            <div className="flex justify-between items-center mb-5 border-b border-border-custom pb-3">
              <h4 className="text-xl font-semibold">Actividad Reciente</h4>
            </div>
            <div className="flex flex-col gap-4">
              <div className="flex gap-4">
                <div className="w-10 h-10 rounded-full bg-status-green/10 flex items-center justify-center text-status-green shrink-0">
                  <TrendingUp className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm mb-1">
                    <strong>Actividad pendiente</strong> de registro.
                  </p>
                  <p className="text-xs text-text-muted">
                    Pronto se mostrará el historial de operaciones.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="w-10 h-10 rounded-full bg-status-yellow/10 flex items-center justify-center text-status-yellow shrink-0">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm mb-1">
                    <strong>Avisos</strong> visibles aquí.
                  </p>
                  <p className="text-xs text-text-muted">
                    Sin alertas por el momento.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
