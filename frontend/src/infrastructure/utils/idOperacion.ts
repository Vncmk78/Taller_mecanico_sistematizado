const UUID_V4 = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';

/**
 * Clave de idempotencia para operaciones de inventario.
 *
 * `crypto.randomUUID()` solo existe en contexto seguro (HTTPS) y en navegadores
 * modernos. En desarrollo por IP o en navegadores antiguos devuelve `undefined`
 * y lanzar `TypeError` justo al liberar/reservar stock. Se mantiene como ruta
 * principal y se degrada a `getRandomValues` (disponible incluso en HTTP) y,
 * como último recurso, a un UUID v4 no criptográfico pero suficientemente
 * único para una clave de idempotencia.
 */
export function generarIdOperacion(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');

    return [
      hex.slice(0, 8),
      hex.slice(8, 12),
      hex.slice(12, 16),
      hex.slice(16, 20),
      hex.slice(20, 32),
    ].join('-');
  }

  return UUID_V4.replace(/[xy]/g, (caracter) => {
    const azar = Math.floor(Math.random() * 16);
    const valor = caracter === 'x' ? azar : (azar & 0x3) | 0x8;
    return valor.toString(16);
  });
}
