export type TipoEvidenciaArchivo = 'imagen' | 'video' | 'desconocido';

export interface LimitesEvidenciaPorTipo {
    maxBytes: number;
    label: string;
    extensiones: string[];
    mimePermitidos: string[];
}

export interface ResultadoValidacionEvidencia {
    valido: boolean;
    error?: string;
    tipo?: TipoEvidenciaArchivo;
    maxBytes?: number;
}

const LIMITES_POR_TIPO: Record<'imagen' | 'video', LimitesEvidenciaPorTipo> = {
    imagen: {
        maxBytes: 5 * 1024 * 1024,
        label: '5 MB',
        extensiones: ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.gif'],
        mimePermitidos: ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/gif'],
    },
    video: {
        maxBytes: 12 * 1024 * 1024,
        label: '12 MB',
        extensiones: ['.mp4', '.webm', '.mov', '.avi', '.mpeg', '.m4v'],
        mimePermitidos: ['video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo', 'video/mpeg', 'video/x-m4v'],
    },
};

const EXTENSIONES_TODAS = [...LIMITES_POR_TIPO.imagen.extensiones, ...LIMITES_POR_TIPO.video.extensiones];

export function obtenerExtension(nombre: string): string {
    const punto = nombre.lastIndexOf('.');
    if (punto === -1) return '';
    return nombre.slice(punto).toLowerCase();
}

export function obtenerTipoPorArchivo(file: File): TipoEvidenciaArchivo {
    const contentType = file.type.toLowerCase();
    if (contentType.startsWith('image/')) return 'imagen';
    if (contentType.startsWith('video/')) return 'video';

    const extension = obtenerExtension(file.name);
    if (LIMITES_POR_TIPO.imagen.extensiones.includes(extension)) return 'imagen';
    if (LIMITES_POR_TIPO.video.extensiones.includes(extension)) return 'video';

    return 'desconocido';
}

export function obtenerLimitesPorTipo(tipo: TipoEvidenciaArchivo): LimitesEvidenciaPorTipo | null {
    if (tipo === 'imagen') return LIMITES_POR_TIPO.imagen;
    if (tipo === 'video') return LIMITES_POR_TIPO.video;
    return null;
}

export function formatearLimitesParaTexto(): string {
    return `Formatos permitidos: imágenes (${LIMITES_POR_TIPO.imagen.extensiones.join(', ')}) y videos (${LIMITES_POR_TIPO.video.extensiones.join(', ')}). Máximo ${LIMITES_POR_TIPO.imagen.label} para imágenes y ${LIMITES_POR_TIPO.video.label} para videos.`;
}

export function validarArchivoEvidencia(file: File | null): ResultadoValidacionEvidencia {
    if (!file) {
        return { valido: false, error: 'Selecciona una foto o un video.' };
    }

    if (file.size <= 0) {
        return { valido: false, error: 'El archivo está vacío.' };
    }

    const tipo = obtenerTipoPorArchivo(file);
    if (tipo === 'desconocido') {
        return { valido: false, error: 'Solo se permiten imágenes o videos.' };
    }

    const limites = obtenerLimitesPorTipo(tipo);
    if (!limites) {
        return { valido: false, error: 'Solo se permiten imágenes o videos.' };
    }

    const extension = obtenerExtension(file.name);
    if (!EXTENSIONES_TODAS.includes(extension)) {
        return { valido: false, error: 'Extensión de archivo no permitida.' };
    }

    if (tipo === 'imagen' && !LIMITES_POR_TIPO.imagen.extensiones.includes(extension)) {
        return { valido: false, error: 'Extensión de archivo no permitida.' };
    }

    if (tipo === 'video' && !LIMITES_POR_TIPO.video.extensiones.includes(extension)) {
        return { valido: false, error: 'Extensión de archivo no permitida.' };
    }

    if (file.size > limites.maxBytes) {
        const tipoLabel = tipo === 'imagen' ? 'imágenes' : 'videos';
        return {
            valido: false,
            error: `El archivo supera el límite de ${limites.label} para ${tipoLabel}.`,
            tipo,
            maxBytes: limites.maxBytes,
        };
    }

    return {
        valido: true,
        tipo,
        maxBytes: limites.maxBytes,
    };
}

export const MAX_BYTES_IMAGEN = LIMITES_POR_TIPO.imagen.maxBytes;
export const MAX_BYTES_VIDEO = LIMITES_POR_TIPO.video.maxBytes;
