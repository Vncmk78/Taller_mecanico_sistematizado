/**
 * Aviso/notificación disponible para el usuario en la interfaz web.
 * Estructura alineada con el contrato esperado de MS1 (notificaciones).
 */
export interface Notification {
  id: string;
  userId: string;
  tipo: string;
  titulo: string;
  mensaje: string;
  leida: boolean;
  creadaEn: string;
  ordenId?: string | null;
  presupuestoId?: string | null;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  noLeidas: number;
}
