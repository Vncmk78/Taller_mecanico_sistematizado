import { Alert } from '@/presentation/components/ui/Alert';
import { getSessionExpiryMessage } from '@/infrastructure/config/sessionExpiry';

/**
 * Aviso persistente mientras la sesión está por vencer. No ofrece "renovar":
 * el backend no tiene refresh ni endpoint de extensión, así que la única salida
 * es guardar el trabajo e iniciar sesión de nuevo cuando corresponda.
 */
export function SessionExpiryBanner({ minutosRestantes }: { minutosRestantes: number | null }) {
  if (minutosRestantes === null) return null;

  return (
    <div className="fixed bottom-6 left-6 z-[70] w-[min(24rem,calc(100vw-3rem))]">
      <Alert tone="warning">{getSessionExpiryMessage(minutosRestantes)}</Alert>
    </div>
  );
}
