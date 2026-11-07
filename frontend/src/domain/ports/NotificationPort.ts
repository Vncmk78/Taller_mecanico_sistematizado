import type { NotificationListResponse } from '@/domain/entities/Notification';

export interface NotificationPort {
  getMyNotifications(params?: { soloNoLeidas?: boolean; limit?: number }): Promise<NotificationListResponse>;
  markAsRead(id: string): Promise<void>;
  markAllAsRead(): Promise<void>;
}
