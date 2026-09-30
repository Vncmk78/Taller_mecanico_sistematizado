import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Alert } from '@/presentation/components/ui/Alert';

describe('Alert: notificación contextual', () => {
  it('muestra el mensaje y usa role="alert"', () => {
    render(<Alert tone="error">Credenciales incorrectas</Alert>);

    expect(screen.getByRole('alert')).toHaveTextContent('Credenciales incorrectas');
  });

  it('muestra una acción cuando se entrega una', () => {
    const handleRetry = vi.fn();
    render(
      <Alert
        tone="warning"
        action={
          <button onClick={handleRetry} type="button">
            Reintentar
          </button>
        }
      >
        No se pudo conectar.
      </Alert>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(handleRetry).toHaveBeenCalled();
  });
});