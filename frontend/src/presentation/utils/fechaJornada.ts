/**
 * `jornada_local` es una fecha sin hora (AAAA-MM-DD) del taller. `new Date()`
 * la leería como medianoche UTC y en Chile mostraría el día anterior.
 */
export function formatJornada(jornada: string): string {
    const [anio, mes, dia] = jornada.split('-').map(Number);
    if (!anio || !mes || !dia) return jornada;
    return new Date(anio, mes - 1, dia).toLocaleDateString('es-CL', {
        day: '2-digit', month: 'short', year: 'numeric',
    });
}
