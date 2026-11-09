import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { notificationService } from '@/infrastructure/api/NotificationService';
import { NotificationDeliveryPanel } from './NotificationDeliveryPanel';
vi.mock('@/infrastructure/api/NotificationService', () => ({ notificationService: { getDeliveries: vi.fn(), retryDeliveries: vi.fn() } }));
const entrega = { id: '3', canal: 'correo' as const, estado: 'sin_configuracion', intentos: 1, aceptadaEn: null, ultimoError: 'proveedor_no_configurado', intentosRegistrados: [] };
beforeEach(() => vi.clearAllMocks());
it('consulta al abrir y distingue aceptación del proveedor de lectura', async () => {
  vi.mocked(notificationService.getDeliveries).mockResolvedValue([{ ...entrega, estado: 'aceptada', aceptadaEn: '2026-11-08T10:00:00Z' }]);
  render(<NotificationDeliveryPanel id="8" />);
  expect(notificationService.getDeliveries).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Ver envíos de correo y push' }));
  expect(await screen.findByText(/Aceptado por el proveedor/)).toBeInTheDocument();
  expect(screen.getByText(/no confirma que la persona lo haya leído/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Reintentar envíos pendientes' })).not.toBeInTheDocument();
});
it('reintentar registra trabajo pendiente sin declarar correo enviado', async () => {
  vi.mocked(notificationService.getDeliveries).mockResolvedValue([entrega]);
  vi.mocked(notificationService.retryDeliveries).mockResolvedValue([{ ...entrega, estado: 'pendiente' }]);
  render(<NotificationDeliveryPanel id="8" />);
  fireEvent.click(screen.getByRole('button', { name: 'Ver envíos de correo y push' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Reintentar envíos pendientes' }));
  expect(await screen.findByText(/Reintento registrado/)).toBeInTheDocument();
  expect(screen.getByText(/Pendiente de envío/)).toBeInTheDocument();
  expect(notificationService.retryDeliveries).toHaveBeenCalledOnce();
  expect(notificationService.retryDeliveries).toHaveBeenCalledWith('8');
});
it('un fallo de consulta se muestra y permite volver a consultar', async () => {
  vi.mocked(notificationService.getDeliveries).mockRejectedValue(new Error('No disponible'));
  render(<NotificationDeliveryPanel id="8" />);
  fireEvent.click(screen.getByRole('button', { name: 'Ver envíos de correo y push' }));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Actualizar estado de envíos' })).toBeEnabled();
});
