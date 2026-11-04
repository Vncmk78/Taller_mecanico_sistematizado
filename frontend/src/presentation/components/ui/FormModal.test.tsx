import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { FormModal } from '@/presentation/components/ui/FormModal';

describe('FormModal: contenedor de formularios modales', () => {
  it('no renderiza nada cuando está cerrado', () => {
    render(
      <FormModal open={false} title="Nuevo repuesto" onClose={() => undefined}>
        <p>Contenido</p>
      </FormModal>
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('expone el diálogo con su título y el contenido', () => {
    render(
      <FormModal open title="Nuevo repuesto" onClose={() => undefined}>
        <p>Contenido del formulario</p>
      </FormModal>
    );

    expect(screen.getByRole('dialog', { name: 'Nuevo repuesto' })).toBeInTheDocument();
    expect(screen.getByText('Contenido del formulario')).toBeInTheDocument();
  });

  it('cierra con el botón de la equis', () => {
    const onClose = vi.fn();
    render(
      <FormModal open title="Editar proveedor" onClose={onClose}>
        <p>Contenido</p>
      </FormModal>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('permite personalizar el ancho de la tarjeta', () => {
    render(
      <FormModal
        open
        title="Movimiento"
        onClose={() => undefined}
        maxWidthClassName="max-w-[600px]"
      >
        <p>Contenido</p>
      </FormModal>
    );

    expect(screen.getByRole('dialog')).toHaveClass('max-w-[600px]');
  });
});
