import { useCallback, useEffect, useState } from 'react';
import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import { getApiErrorMessage, isNotFoundError } from '@/infrastructure/api/errors';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';

export type CargaSolicitud =
    | { estado: 'cargando' }
    | { estado: 'no_encontrada' }
    | { estado: 'error'; mensaje: string }
    | { estado: 'lista'; solicitud: SolicitudNuevaAtencion };

export interface UseSolicitudNuevaAtencionResult {
    carga: CargaSolicitud;
    /** Vuelve a cargar mostrando el estado de carga (reintento de la página). */
    recargar: () => void;
    /** Reemplaza la solicitud mostrada por la que devolvió el servidor. */
    reemplazar: (solicitud: SolicitudNuevaAtencion) => void;
    /**
     * Consulta el GET de la solicitud sin ocultar la pantalla (comprobación tras
     * una respuesta perdida). Devuelve la solicitud actual o null si falló.
     */
    comprobar: () => Promise<SolicitudNuevaAtencion | null>;
}

/** Carga de una solicitud de nueva atención (GET /ordenes/nuevas-atenciones/{id}). */
export function useSolicitudNuevaAtencion(id: string | undefined): UseSolicitudNuevaAtencionResult {
    const [carga, setCarga] = useState<CargaSolicitud>({ estado: 'cargando' });
    const [reintento, setReintento] = useState(0);

    useEffect(() => {
        if (!id) return;
        let activo = true;
        nuevaAtencionService
            .obtener(id)
            .then((solicitud) => {
                if (activo) setCarga({ estado: 'lista', solicitud });
            })
            .catch((err: unknown) => {
                if (!activo) return;
                setCarga(
                    isNotFoundError(err)
                        ? { estado: 'no_encontrada' }
                        : { estado: 'error', mensaje: getApiErrorMessage(err, 'No se pudo cargar la solicitud.') }
                );
            });
        return () => {
            activo = false;
        };
    }, [id, reintento]);

    const recargar = useCallback(() => {
        setCarga({ estado: 'cargando' });
        setReintento((n) => n + 1);
    }, []);

    const reemplazar = useCallback((solicitud: SolicitudNuevaAtencion) => {
        setCarga({ estado: 'lista', solicitud });
    }, []);

    const comprobar = useCallback(async () => {
        if (!id) return null;
        try {
            const solicitud = await nuevaAtencionService.obtener(id);
            setCarga({ estado: 'lista', solicitud });
            return solicitud;
        } catch {
            return null;
        }
    }, [id]);

    return { carga, recargar, reemplazar, comprobar };
}
