import { RotateCcw } from 'lucide-react';
import { ListadoSolicitudes } from '@/presentation/components/nuevaAtencion/ListadoSolicitudes';
import { RUTA_SOLICITUDES_ADMIN } from '@/presentation/components/nuevaAtencion/rutasNuevaAtencion';

/**
 * Solicitudes de nueva atención de todos los clientes (portal Administrador).
 * MS2 da el alcance administrativo a cualquier cuenta con rol Administrador,
 * también multirrol; no depende del perfil Cliente.
 */
export function AdminNuevasAtencionesPage() {
    return (
        <div className="animate-fade-in p-4 sm:p-6 lg:p-10">
            <header className="mb-6">
                <h1 className="text-3xl font-bold flex items-center gap-3">
                    <RotateCcw className="w-7 h-7 text-text-muted" aria-hidden />
                    Solicitudes de nueva atención
                </h1>
                <p className="text-text-muted mt-2">
                    Solicitudes de todos los clientes después de una cancelación. Revise las pendientes y genere la
                    orden de las aceptadas.
                </p>
            </header>

            <ListadoSolicitudes
                rutaDetalle={(id) => `${RUTA_SOLICITUDES_ADMIN}/${id}`}
                filtrosPorOrden
                mostrarCliente
                vacio={{ descripcion: 'Los clientes las envían desde el detalle de una orden cancelada.' }}
            />
        </div>
    );
}
