import { Link } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { ListadoSolicitudes } from '@/presentation/components/nuevaAtencion/ListadoSolicitudes';
import { RUTA_SOLICITUDES_CLIENTE } from '@/presentation/components/nuevaAtencion/rutasNuevaAtencion';
import { hasAnyRole } from '@/presentation/utils/roleVisibility';

/**
 * Listado de solicitudes de nueva atención del portal Cliente. El alcance lo
 * decide MS2: un Cliente ve las propias y una cuenta que incluye Administrador
 * ve todas, por eso el encabezado lo indica en ese caso.
 */
export function ClientNuevasAtencionesPage() {
    const user = useAuthStore((s) => s.user);
    const alcanceAdministrativo = hasAnyRole(user, 'administrador');

    return (
        <div className="animate-fade-in p-4 sm:p-6 lg:p-10">
            <header className="mb-6">
                <h1 className="text-3xl font-bold flex items-center gap-3">
                    <RotateCcw className="w-7 h-7 text-text-muted" aria-hidden />
                    {alcanceAdministrativo ? 'Solicitudes de nueva atención' : 'Mis solicitudes de nueva atención'}
                </h1>
                <p className="text-text-muted mt-2">
                    {alcanceAdministrativo
                        ? 'Su cuenta incluye el rol Administrador: se muestran las solicitudes de todos los clientes.'
                        : 'Solicitudes enviadas después de una cancelación. Cada una queda pendiente hasta que el taller la revise.'}
                </p>
            </header>

            <ListadoSolicitudes
                rutaDetalle={(id) => `${RUTA_SOLICITUDES_CLIENTE}/${id}`}
                mostrarCliente={alcanceAdministrativo}
                vacio={{
                    descripcion: 'Puede solicitar una nueva atención desde el detalle de una orden cancelada.',
                    accion: (
                        <Link to="/client/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                            Ir a mis órdenes
                        </Link>
                    ),
                }}
            />
        </div>
    );
}
