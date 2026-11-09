import { useState } from 'react';
import type { NotificationDelivery } from '@/domain/entities/Notification';
import { notificationService } from '@/infrastructure/api/NotificationService';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { Button } from '@/presentation/components/ui/Button';

const ESTADOS: Record<string, string> = {
  pendiente: 'Pendiente de envío', procesando: 'En proceso', aceptada: 'Aceptado por el proveedor',
  fallida: 'Envío sin confirmar', sin_configuracion: 'Proveedor sin configurar',
  sin_dispositivo: 'Sin dispositivo registrado', omitida: 'No enviado: destinatario o dispositivo no disponible',
};

export function NotificationDeliveryPanel({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationDelivery[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const cargar = async (reintentar = false) => {
    if (busy) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      setItems(await (reintentar ? notificationService.retryDeliveries(id) : notificationService.getDeliveries(id)));
      if (reintentar) setMessage('Reintento registrado. Actualice el estado para consultar el resultado.');
    } catch (err) { setError(getApiErrorMessage(err, 'No se pudo consultar el envío.')); }
    finally { setBusy(false); }
  };
  return <section className="mt-3 border-t border-border-custom pt-3" aria-label="Envíos del aviso">
    <button type="button" className="text-sm text-primary-blue" aria-expanded={open} onClick={() => {
      setOpen(!open); if (!open && items === null) void cargar();
    }}>Ver envíos de correo y push</button>
    {open && <div className="text-sm mt-3 space-y-2">
      {error && <p role="alert" className="text-status-red">{error}</p>}
      {message && <p role="status">{message}</p>}
      {items?.length === 0 && <p>Este aviso no tiene intentos de envío registrados.</p>}
      {items?.map(e => <div key={e.id}>
        <p><strong>{e.canal === 'correo' ? 'Correo' : 'Push'}:</strong> {ESTADOS[e.estado] ?? e.estado} · Intentos: {e.intentos}</p>
        {e.aceptadaEn && <p>Aceptado: {new Date(e.aceptadaEn).toLocaleString('es-CL')}</p>}
        {e.intentosRegistrados.length > 0 && <details><summary>Historial de intentos</summary><ul>
          {e.intentosRegistrados.map(i => <li key={i.numero}>Intento {i.numero}: {ESTADOS[i.resultado] ?? i.resultado}</li>)}
        </ul></details>}
      </div>)}
      <p className="text-xs text-text-muted">La aceptación del proveedor no confirma que la persona lo haya leído.</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" isLoading={busy} onClick={() => void cargar()}>Actualizar estado de envíos</Button>
        {items?.some(e => ['fallida', 'sin_configuracion', 'sin_dispositivo'].includes(e.estado)) &&
          <Button variant="secondary" disabled={busy} onClick={() => void cargar(true)}>Reintentar envíos pendientes</Button>}
      </div>
    </div>}
  </section>;
}
