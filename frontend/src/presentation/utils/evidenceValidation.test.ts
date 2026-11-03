import { describe, expect, it } from 'vitest';
import { validarArchivoEvidencia } from './evidenceValidation';

function archivo(nombre: string, type: string, size = 1024): File {
    const file = new File(['contenido'], nombre, { type });
    Object.defineProperty(file, 'size', { value: size });
    return file;
}

describe('Validación de evidencia según contrato MS4/Gateway', () => {
    it.each([
        ['foto.jpg', 'image/jpeg'], ['foto.JPEG', 'image/jpeg'],
        ['foto.png', 'image/png'], ['foto.webp', 'image/webp'],
        ['video.mp4', 'video/mp4'], ['video.mov', 'video/quicktime'],
        ['video.mov', 'video/mp4'], ['video.mp4', 'video/quicktime'],
    ])('acepta %s con MIME %s', (nombre, mime) => {
        expect(validarArchivoEvidencia(archivo(nombre, mime)).valido).toBe(true);
    });

    it.each([
        ['foto.gif', 'image/gif'], ['foto.heic', 'image/heic'],
        ['video.webm', 'video/webm'], ['video.avi', 'video/x-msvideo'],
        ['foto.svg', 'image/svg+xml'], ['foto.jpg', 'image/svg+xml'],
        ['foto.jpg', 'application/octet-stream'], ['foto.jpg', ''],
        ['video.jpg', 'video/mp4'], ['foto.mp4', 'image/jpeg'],
    ])('rechaza %s con MIME %s antes de enviar', (nombre, mime) => {
        expect(validarArchivoEvidencia(archivo(nombre, mime)).valido).toBe(false);
    });

    it('acepta una foto de 10 MiB y rechaza un byte más', () => {
        expect(validarArchivoEvidencia(archivo('foto.jpg', 'image/jpeg', 10 * 1024 * 1024)).valido).toBe(true);
        expect(validarArchivoEvidencia(archivo('foto.jpg', 'image/jpeg', 10 * 1024 * 1024 + 1))).toMatchObject({
            valido: false, error: 'El archivo supera el límite de 10 MB para imágenes.',
        });
    });

    it('rechaza videos mayores al techo de 12 MiB de la Gateway', () => {
        expect(validarArchivoEvidencia(archivo('video.mp4', 'video/mp4', 12 * 1024 * 1024 + 1))).toMatchObject({
            valido: false, error: 'El archivo supera el límite de 12 MB para videos.',
        });
    });

    it('rechaza un archivo vacío', () => {
        expect(validarArchivoEvidencia(archivo('foto.jpg', 'image/jpeg', 0))).toMatchObject({
            valido: false, error: 'El archivo está vacío.',
        });
    });
});
