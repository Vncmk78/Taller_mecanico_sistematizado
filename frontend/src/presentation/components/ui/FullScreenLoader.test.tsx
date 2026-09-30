import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FullScreenLoader } from '@/presentation/components/ui/FullScreenLoader';

describe('FullScreenLoader: pantalla completa de carga', () => {
  it('muestra el mensaje por defecto', () => {
    render(<FullScreenLoader />);

    expect(screen.getByText('Verificando sesión...')).toBeInTheDocument();
  });

  it('muestra un mensaje personalizado', () => {
    render(<FullScreenLoader message="Cargando tu panel..." />);

    expect(screen.getByText('Cargando tu panel...')).toBeInTheDocument();
  });
});