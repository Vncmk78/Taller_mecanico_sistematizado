import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SessionExpiryBanner } from './SessionExpiryBanner';

describe('SessionExpiryBanner: aviso previo a la expiración', () => {
  it('no renderiza nada mientras la sesión no está por vencer', () => {
    const { container } = render(<SessionExpiryBanner minutosRestantes={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('muestra los minutos restantes con tono de advertencia', () => {
    render(<SessionExpiryBanner minutosRestantes={5} />);

    const aviso = screen.getByRole('alert');
    expect(aviso).toHaveTextContent(
      'Tu sesión expirará en 5 minutos. Guarda tu trabajo e inicia sesión nuevamente.'
    );
  });

  it('con un minuto o menos no muestra una cifra', () => {
    render(<SessionExpiryBanner minutosRestantes={1} />);

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Tu sesión está por expirar. Guarda tu trabajo e inicia sesión nuevamente.'
    );
  });
});
