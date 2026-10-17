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

  it('muestra el mensaje real de la Gateway sin reemplazarlo por un texto genérico', () => {
    // Es el texto que escribe el backend para un 503: el banner debe respetarlo
    // en vez de rotularlo como "sin conexión", porque la Gateway está viva.
    render(
      <OfflineBanner
        message="La Gateway está ocupada. Intente más tarde."
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByRole('alert')).toHaveTextContent('La Gateway está ocupada. Intente más tarde.');
    expect(screen.queryByText(/Verifique su conexión/)).not.toBeInTheDocument();
  });

  it('agrega la referencia de la petición cuando la Gateway la envía', () => {
    render(<OfflineBanner message="La Gateway está ocupada." onRetry={vi.fn()} requestId="req-abc-123" />);

    expect(screen.getByText('Referencia: req-abc-123')).toBeInTheDocument();
  });

  it('omite la referencia en un fallo de red que no trae request_id', () => {
    render(<OfflineBanner message="No se pudo conectar con el servidor." onRetry={vi.fn()} requestId={null} />);

    expect(screen.queryByText(/Referencia:/)).not.toBeInTheDocument();
  });
});
