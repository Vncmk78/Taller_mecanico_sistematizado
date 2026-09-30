import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';

describe('ConfirmDialog: confirmación de acciones', () => {
  it('muestra el título y la descripción', () => {
    render(
      <ConfirmDialog
        open
        title="¿Eliminar orden?"
        description="Esta acción no se puede deshacer."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('dialog', { name: '¿Eliminar orden?' })).toBeInTheDocument();
    expect(screen.getByText('Esta acción no se puede deshacer.')).toBeInTheDocument();
  });

  it('llama onConfirm al confirmar', () => {
    const handleConfirm = vi.fn();
    const handleCancel = vi.fn();
    render(
      <ConfirmDialog open title="Confirmar" onConfirm={handleConfirm} onCancel={handleCancel} />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }));
    expect(handleConfirm).toHaveBeenCalled();
    expect(handleCancel).not.toHaveBeenCalled();
  });

  it('llama onCancel al cancelar', () => {
    const handleCancel = vi.fn();
    render(
      <ConfirmDialog open title="Confirmar" onConfirm={vi.fn()} onCancel={handleCancel} />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(handleCancel).toHaveBeenCalled();
  });

  it('cierra con la tecla Escape', () => {
    const handleCancel = vi.fn();
    render(
      <ConfirmDialog open title="Confirmar" onConfirm={vi.fn()} onCancel={handleCancel} />
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(handleCancel).toHaveBeenCalled();
  });

  it('cierra al hacer clic fuera del diálogo', () => {
    const handleCancel = vi.fn();
    const { container } = render(
      <ConfirmDialog open title="Confirmar" onConfirm={vi.fn()} onCancel={handleCancel} />
    );

    fireEvent.mouseDown(container.firstElementChild as HTMLElement);
    expect(handleCancel).toHaveBeenCalled();
  });

  it('no cierra al hacer clic dentro del diálogo', () => {
    const handleCancel = vi.fn();
    render(
      <ConfirmDialog open title="Confirmar" onConfirm={vi.fn()} onCancel={handleCancel} />
    );

    fireEvent.mouseDown(screen.getByRole('dialog'));
    expect(handleCancel).not.toHaveBeenCalled();
  });

  it('cierra con el botón X', () => {
    const handleCancel = vi.fn();
    render(
      <ConfirmDialog open title="Confirmar" onConfirm={vi.fn()} onCancel={handleCancel} />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }));
    expect(handleCancel).toHaveBeenCalled();
  });

  it('deshabilita las acciones y evita confirmar mientras isLoading', () => {
    const handleConfirm = vi.fn();
    const handleCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Confirmar"
        onConfirm={handleConfirm}
        onCancel={handleCancel}
        isLoading
      />
    );

    const confirmButton = screen.getByRole('button', { name: 'Cargando...' });
    expect(confirmButton).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeDisabled();

    fireEvent.click(confirmButton);
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(handleConfirm).not.toHaveBeenCalled();
    expect(handleCancel).not.toHaveBeenCalled();
  });

  it('no renderiza nada cuando está cerrado', () => {
    render(<ConfirmDialog open={false} title="Confirmar" onConfirm={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});