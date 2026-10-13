/** Tamaño de archivo legible en español, sin decimales para bytes. */
export function formatBytes(bytes: number): string {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / 1024 ** i;
    return `${value.toLocaleString('es-CL', { maximumFractionDigits: i === 0 ? 0 : 1 })} ${units[i]}`;
}
