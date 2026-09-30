import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
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
});