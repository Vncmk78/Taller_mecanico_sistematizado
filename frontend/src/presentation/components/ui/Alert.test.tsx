import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Alert, type AlertTone } from '@/presentation/components/ui/Alert';

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

  const toneCases: Array<[AlertTone, string]> = [
    ['error', 'text-status-red'],
    ['success', 'text-status-green'],
    ['warning', 'text-status-yellow'],
    ['info', 'text-status-blue'],
    ['orange', 'text-status-orange'],
  ];

  it.each(toneCases)(
    'el tono %s aplica las clases de color correspondientes',
    (tone, expectedClass) => {
      render(<Alert tone={tone}>{tone}</Alert>);

      expect(screen.getByRole('alert').className).toContain(expectedClass);
    }
  );
});