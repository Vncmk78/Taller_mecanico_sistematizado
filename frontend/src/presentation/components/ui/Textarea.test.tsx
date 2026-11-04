import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Textarea } from '@/presentation/components/ui/Textarea';

describe('Textarea: área de texto accesible', () => {
  it('asocia el label con el textarea mediante id generado', () => {
    render(<Textarea label="Descripción" />);

    expect(screen.getByLabelText('Descripción')).toBeInTheDocument();
  });

  it('marca aria-invalid y describe el error cuando existe', () => {
    render(<Textarea label="Descripción" error="Describe la entrada" />);

    const textarea = screen.getByLabelText('Descripción');
    expect(textarea).toHaveAttribute('aria-invalid', 'true');

    const errorId = textarea.getAttribute('aria-describedby');
    expect(errorId).toBeTruthy();
    expect(document.getElementById(errorId as string)).toHaveTextContent('Describe la entrada');
  });

  it('anuncia el error con role="alert"', () => {
    render(<Textarea label="Descripción" error="Campo obligatorio" />);

    expect(screen.getByRole('alert')).toHaveTextContent('Campo obligatorio');
  });

  it('no marca aria-invalid ni aria-describedby cuando no hay error', () => {
    render(<Textarea label="Observación" />);

    const textarea = screen.getByLabelText('Observación');
    expect(textarea).not.toHaveAttribute('aria-invalid');
    expect(textarea).not.toHaveAttribute('aria-describedby');
  });

  it('describe el campo con la ayuda y conserva las descripciones externas', () => {
    render(
      <Textarea
        label="Detalle"
        hint="Máximo 500 caracteres"
        aria-describedby="ayuda-externa"
      />
    );

    const textarea = screen.getByLabelText('Detalle');
    const ids = (textarea.getAttribute('aria-describedby') ?? '').split(' ');

    expect(ids).toContain('ayuda-externa');
    expect(ids).toHaveLength(2);
    expect(document.getElementById(ids[1])).toHaveTextContent('Máximo 500 caracteres');
  });

  it('expone required y aria-required cuando el campo es obligatorio', () => {
    render(<Textarea label="Descripción" required />);

    const textarea = screen.getByLabelText('Descripción');
    expect(textarea).toBeRequired();
    expect(textarea).toHaveAttribute('aria-required', 'true');
  });
});
