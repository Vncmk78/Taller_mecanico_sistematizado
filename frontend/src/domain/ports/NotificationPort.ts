import type { NotificationDelivery, NotificationListResponse } from '@/domain/entities/Notification';

export interface NotificationPort {
  getDeliveries(id: string): Promise<NotificationDelivery[]>;
  retryDeliveries(id: string): Promise<NotificationDelivery[]>;
  getMyNotifications(params?: { soloNoLeidas?: boolean; limit?: number }): Promise<NotificationListResponse>;
  markAsRead(id: string): Promise<void>;
  markAllAsRead(): Promise<void>;
}
