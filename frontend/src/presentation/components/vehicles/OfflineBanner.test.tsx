import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';

describe('OfflineBanner: aviso de datos locales sin conexión', () => {
  it('muestra el mensaje de error y el aviso de datos locales', () => {
    render(<OfflineBanner message="No se pudo conectar con el servidor." onRetry={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo conectar con el servidor.');
    expect(screen.getByText(/Mostrando datos disponibles localmente/)).toBeInTheDocument();
  });

  it('usa un mensaje por defecto cuando no hay error', () => {
    render(<OfflineBanner message={null} onRetry={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo conectar con el servidor.');
    expect(screen.getByText(/Mostrando datos disponibles localmente/)).toBeInTheDocument();
  });

  it('llama onRetry al presionar Reintentar', () => {
    const handleRetry = vi.fn();
    render(<OfflineBanner message="Error de red" onRetry={handleRetry} />);

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(handleRetry).toHaveBeenCalled();
  });
});