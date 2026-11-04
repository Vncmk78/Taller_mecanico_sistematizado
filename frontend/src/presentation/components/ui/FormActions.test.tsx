import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FormActions } from '@/presentation/components/ui/FormActions';

describe('FormActions: fila de acciones del formulario', () => {
  it('renderiza las acciones recibidas', () => {
    render(
      <FormActions>
        <button type="button">Cancelar</button>
        <button type="submit">Guardar</button>
      </FormActions>
    );

    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeInTheDocument();
  });

  it('permite añadir clases al contenedor', () => {
    const { container } = render(
      <FormActions className="mt-4">
        <button type="submit">Guardar</button>
      </FormActions>
    );

    expect(container.firstChild).toHaveClass('mt-4');
  });
});
