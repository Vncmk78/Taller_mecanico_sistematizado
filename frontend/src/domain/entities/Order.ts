export type OrderStatus =
  | 'recibido'
  | 'esperando_diagnostico'
  | 'esperando_aprobacion'
  | 'esperando_repuestos'
  | 'en_reparacion'
  | 'listo'
  | 'entregado'
  | 'cancelado';

export interface Order {
  id: string;
  vehicleId: string;
  mechanicId?: string;
  status: OrderStatus;
  description: string;
  createdAt: string;
  updatedAt: string;
}
