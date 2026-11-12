import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Alert, type AlertTone } from '@/presentation/components/ui/Alert';

describe('Alert: notificación contextual', () => {
  it('error usa role="alert" (assertivo)', () => {
    render(<Alert tone="error">Credenciales incorrectas</Alert>);

    expect(screen.getByRole('alert')).toHaveTextContent('Credenciales incorrectas');
  });

  it('warning usa role="alert" (assertivo)', () => {
    render(<Alert tone="warning">No se pudo conectar.</Alert>);

    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo conectar.');
  });

  it('success usa role="status" (polite)', () => {
    render(<Alert tone="success">Vehículo registrado con éxito.</Alert>);

    expect(screen.getByRole('status')).toHaveTextContent('Vehículo registrado con éxito.');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('info y orange usan role="status" (polite)', () => {
    const { unmount } = render(<Alert tone="info">Información</Alert>);
    expect(screen.getByRole('status')).toHaveTextContent('Información');

    unmount();
    render(<Alert tone="orange">Aviso</Alert>);
    expect(screen.getByRole('status')).toHaveTextContent('Aviso');
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

  it('marca aria-atomic para anunciar siempre el mensaje completo', () => {
    render(<Alert tone="error">No se pudo guardar.</Alert>);

    expect(screen.getByRole('alert')).toHaveAttribute('aria-atomic', 'true');
  });

  it('acepta un id para asociarlo desde el campo que lo origina', () => {
    render(
      <Alert tone="error" id="campo-error">
        Revisa el campo.
      </Alert>
    );

    expect(document.getElementById('campo-error')).toHaveTextContent('Revisa el campo.');
  });

  const toneCases: Array<[AlertTone, string, string]> = [
    ['error', 'text-status-red', 'alert'],
    ['warning', 'text-status-yellow', 'alert'],
    ['success', 'text-status-green', 'status'],
    ['info', 'text-status-blue', 'status'],
    ['orange', 'text-status-orange', 'status'],
  ];

  it.each(toneCases)(
    'el tono %s aplica las clases de color y el rol %s correctos',
    (tone, expectedClass, expectedRole) => {
      const { container } = render(<Alert tone={tone}>{tone}</Alert>);

      const element = container.querySelector<HTMLElement>(`[role="${expectedRole}"]`);
      expect(element).not.toBeNull();
      expect(element?.className).toContain(expectedClass);
    }
  );
});