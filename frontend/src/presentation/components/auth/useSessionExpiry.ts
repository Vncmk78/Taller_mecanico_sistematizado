import { useEffect, useRef, useState } from 'react';
import {
  getTokenExpiryMs,
  SESSION_TICK_MS,
  SESSION_WARNING_MS,
} from '@/infrastructure/config/sessionExpiry';

interface UseSessionExpiryOptions {
  /** Token vigente del store; al cambiar, el temporizador se rearma. */
  token: string | null;
  /**
   * Se llama una sola vez por token cuando la sesión vence.
   * `duranteElUso` distingue la expiración de una sesión que estaba activa
   * (hay que avisar) de un token que ya llegó vencido al abrir la app.
   */
  onExpired: (duranteElUso: boolean) => void;
}

interface AvisoRestante {
  token: string;
  minutos: number;
}

/**
 * Cierra la sesión en el momento en que vence el `exp` del JWT, sin esperar a
 * que la próxima petición reciba un 401 (una pantalla sin tráfico podía seguir
 * mostrando datos de una sesión muerta). También expone los minutos restantes
 * durante la ventana de aviso.
 */
export function useSessionExpiry({ token, onExpired }: UseSessionExpiryOptions): {
  minutosRestantes: number | null;
} {
  // El aviso se guarda junto al token que lo produjo: así un cambio de token
  // descarta el aviso anterior durante el render, sin un setState dentro del
  // efecto que dispararía un render en cascada.
  const [aviso, setAviso] = useState<AvisoRestante | null>(null);
  const onExpiredRef = useRef(onExpired);

  useEffect(() => {
    onExpiredRef.current = onExpired;
  }, [onExpired]);

  useEffect(() => {
    if (!token) return;
    const expiraEn = getTokenExpiryMs(token);
    // Token opaco o sin exp: no se puede anticipar; el 401 reactivo sigue vigente.
    if (expiraEn === null) return;

    const restante = expiraEn - Date.now();
    if (restante <= 0) {
      // La app se abrió con un token ya vencido: se limpia sin anunciar
      // "sesión expirada", porque nunca hubo una sesión en uso que expirar.
      onExpiredRef.current(false);
      return;
    }

    let expirada = false;
    let avisoProgramado: ReturnType<typeof setTimeout> | null = null;
    let intervalo: ReturnType<typeof setInterval> | null = null;
    let temporizadorExpiracion: ReturnType<typeof setTimeout> | null = null;

    const detener = () => {
      if (avisoProgramado !== null) {
        clearTimeout(avisoProgramado);
        avisoProgramado = null;
      }
      if (intervalo !== null) {
        clearInterval(intervalo);
        intervalo = null;
      }
      if (temporizadorExpiracion !== null) {
        clearTimeout(temporizadorExpiracion);
        temporizadorExpiracion = null;
      }
    };

    const finalizar = () => {
      if (expirada) return;
      expirada = true;
      detener();
      setAviso(null);
      onExpiredRef.current(true);
    };

    const actualizar = () => {
      if (expirada) return;
      const restanteAhora = expiraEn - Date.now();
      if (restanteAhora <= 0) {
        finalizar();
        return;
      }
      setAviso({ token, minutos: Math.max(1, Math.ceil(restanteAhora / 60_000)) });
    };

    temporizadorExpiracion = setTimeout(finalizar, restante);
    avisoProgramado = setTimeout(
      () => {
        actualizar();
        intervalo = setInterval(actualizar, SESSION_TICK_MS);
      },
      Math.max(0, restante - SESSION_WARNING_MS)
    );

    // En pestañas en segundo plano los temporizadores se frenan; al volver a
    // primer plano se recalcula de inmediato por si el vencimiento ya pasó.
    const alCambiarVisibilidad = () => {
      if (document.visibilityState === 'visible') actualizar();
    };
    document.addEventListener('visibilitychange', alCambiarVisibilidad);

    return () => {
      expirada = true;
      detener();
      document.removeEventListener('visibilitychange', alCambiarVisibilidad);
    };
  }, [token]);

  const minutosRestantes = aviso && aviso.token === token ? aviso.minutos : null;

  return { minutosRestantes };
}
