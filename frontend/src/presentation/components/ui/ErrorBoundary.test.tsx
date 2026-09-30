import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ErrorBoundary } from '@/presentation/components/ui/ErrorBoundary';

function ComponenteQueExplota(): never {
  throw new Error('boom');
}

function ComponenteSano() {
  return <p>Contenido sin errores</p>;
}

describe('ErrorBoundary: manejo de errores de render', () => {
  it('muestra el fallback por defecto cuando un hijo lanza un error', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ComponenteQueExplota />
      </ErrorBoundary>
    );

    expect(screen.getByRole('heading', { name: 'Algo salió mal' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Recargar página' })
    ).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it('muestra un fallback personalizado cuando se entrega uno', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary fallback={<p>Fallback del equipo</p>}>
        <ComponenteQueExplota />
      </ErrorBoundary>
    );

    expect(screen.getByText('Fallback del equipo')).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it('renderiza el árbol sano sin interferir', () => {
    render(
      <ErrorBoundary>
        <ComponenteSano />
      </ErrorBoundary>
    );

    expect(screen.getByText('Contenido sin errores')).toBeInTheDocument();
  });

  it('Recargar página invoca window.location.reload', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const reloadSpy = vi.fn();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { reload: reloadSpy },
      writable: true,
    });
    render(
      <ErrorBoundary>
        <ComponenteQueExplota />
      </ErrorBoundary>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Recargar página' }));

    expect(reloadSpy).toHaveBeenCalledTimes(1);
    consoleSpy.mockRestore();
  });

  it('no vuelca el token de acceso en la consola', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    // Un AxiosError lleva `config.headers.Authorization` dentro. Si el
    // ErrorBoundary imprimiera el objeto entero, el navegador mostraría esa
    // propiedad al expandirlo en la consola, que es lo que se ve al compartir
    // pantalla. Comprobarla exige recorrer la estructura: `String(error)` solo
    // devuelve el mensaje y no delata el token que va anidado.
    const token = 'eyJhbGciOiJIUzI1NiJ9.token-falso.firma-falsa';
    function ComponenteQueLanzaAxios(): never {
      throw Object.assign(new Error('Request failed with status code 401'), {
        config: { headers: { Authorization: `Bearer ${token}` } },
        response: { status: 401, data: { detail: 'No se proporcionó un token de acceso' } },
      });
    }

    render(
      <ErrorBoundary>
        <ComponenteQueLanzaAxios />
      </ErrorBoundary>
    );

    expect(consoleSpy).toHaveBeenCalled();
    // Solo se examina la llamada del propio ErrorBoundary. React registra además
    // el error lanzado con su propio `console.error("%o\n\n%s\n\n%s\n", error, ...)`,
    // y ese sí incluye el objeto completo: es comportamiento del framework en
    // desarrollo y queda anotado en docs/estudio-seguridad-transporte.md.
    const propias = consoleSpy.mock.calls.filter(
      (argumentos) => argumentos[0] === 'Error capturado por ErrorBoundary:'
    );
    expect(propias).toHaveLength(1);
    const argumentos = propias[0].slice(1);
    // Se serializa el objeto entero (sin `stack`, que es ruido) para detectar
    // el token si está en alguna propiedad anidada.
    const estructura = JSON.stringify(argumentos, (clave, valor) =>
      clave === 'stack' ? undefined : valor
    );
    expect(estructura).not.toContain(token);
    // Lo útil para depurar se conserva: nombre del error y mensaje.
    const texto = argumentos.map((argumento) => String(argumento)).join(' ');
    expect(texto).toContain('Request failed with status code 401');
    consoleSpy.mockRestore();
  });
});