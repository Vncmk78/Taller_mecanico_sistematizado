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
  creado_en?: string;
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
    creadaEn: n.creado_en ?? n.creada_en ?? n.created_at ?? '',
    ordenId: n.orden_id != null ? String(n.orden_id) : null,
    presupuestoId: n.presupuesto_id != null ? String(n.presupuesto_id) : null,
  };
}

class NotificationService implements NotificationPort {
  async getMyNotifications(params?: { soloNoLeidas?: boolean; limit?: number }): Promise<NotificationListResponse> {
    const response = await apiClient.get<NotificacionesRespuestaApi | NotificacionApi[]>('/notificaciones', {
        params: {
          solo_no_leidas: params?.soloNoLeidas ?? undefined,
          limite: params?.limit ?? 20,
        },
      });
      const data = response.data;
      if (Array.isArray(data)) {
        const items = data.map(mapNotificacion);
        return {
          items,
          total: Number(response.headers?.['x-notificaciones-total'] ?? items.length),
          noLeidas: Number(response.headers?.['x-notificaciones-no-leidas'] ?? items.filter((i) => !i.leida).length),
        };
      }
      const items = (data.items ?? []).map(mapNotificacion);
      return {
        items,
        total: data.total ?? items.length,
        noLeidas: data.no_leidas ?? data.unread_count ?? items.filter((i) => !i.leida).length,
      };
  }

  async markAsRead(id: string): Promise<void> {
    await apiClient.patch(`/notificaciones/${id}/leer`);
  }

  async markAllAsRead(): Promise<void> {
    await apiClient.patch('/notificaciones/leer-todas');
  }
}

export const notificationService = new NotificationService();
