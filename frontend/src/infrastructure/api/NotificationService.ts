import type { Notification, NotificationListResponse } from '@/domain/entities/Notification';
import type { NotificationPort } from '@/domain/ports/NotificationPort';
import apiClient from '../config/apiClient';

interface NotificacionApi {
  notificacion_id: number | string;
  usuario_id?: number | string;
  tipo: string;
  titulo: string;
  mensaje: string;
  leida: boolean;
  creada_en?: string;
  created_at?: string;
  orden_id?: number | string | null;
  presupuesto_id?: number | string | null;
}

interface NotificacionesRespuestaApi {
  items?: NotificacionApi[];
  total?: number;
  no_leidas?: number;
  unread_count?: number;
}

function mapNotificacion(n: NotificacionApi): Notification {
  return {
    id: String(n.notificacion_id),
    userId: n.usuario_id != null ? String(n.usuario_id) : '',
    tipo: n.tipo,
    titulo: n.titulo,
    mensaje: n.mensaje,
    leida: Boolean(n.leida),
    creadaEn: n.creada_en ?? n.created_at ?? new Date().toISOString(),
    ordenId: n.orden_id != null ? String(n.orden_id) : null,
    presupuestoId: n.presupuesto_id != null ? String(n.presupuesto_id) : null,
  };
}

class NotificationService implements NotificationPort {
  async getMyNotifications(params?: { soloNoLeidas?: boolean; limit?: number }): Promise<NotificationListResponse> {
    try {
      const response = await apiClient.get<NotificacionesRespuestaApi | NotificacionApi[]>('/notificaciones', {
        params: {
          solo_no_leidas: params?.soloNoLeidas ?? undefined,
          limit: params?.limit ?? 20,
        },
      });
      const data = response.data;
      if (Array.isArray(data)) {
        const items = data.map(mapNotificacion);
        return {
          items,
          total: items.length,
          noLeidas: items.filter((i) => !i.leida).length,
        };
      }
      const items = (data.items ?? []).map(mapNotificacion);
      return {
        items,
        total: data.total ?? items.length,
        noLeidas: data.no_leidas ?? data.unread_count ?? items.filter((i) => !i.leida).length,
      };
    } catch (error: unknown) {
      // Endpoint puede no estar disponible en todos los entornos; degradar con lista vacía.
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 404 || status === 501 || status === 405) {
        return { items: [], total: 0, noLeidas: 0 };
      }
      throw error;
    }
  }

  async markAsRead(id: string): Promise<void> {
    try {
      await apiClient.patch(`/notificaciones/${id}/leer`);
    } catch (error: unknown) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 404 || status === 501 || status === 405) return;
      throw error;
    }
  }

  async markAllAsRead(): Promise<void> {
    try {
      await apiClient.patch('/notificaciones/leer-todas');
    } catch (error: unknown) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 404 || status === 501 || status === 405) return;
      throw error;
    }
  }
}

export const notificationService = new NotificationService();
