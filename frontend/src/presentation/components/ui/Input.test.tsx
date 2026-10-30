import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Input } from '@/presentation/components/ui/Input';

describe('Input: campo de formulario accesible', () => {
  it('asocia el label con el input mediante id generado', () => {
    render(<Input label="Correo Electrónico" />);

    expect(screen.getByLabelText('Correo Electrónico')).toBeInTheDocument();
  });

  it('marca aria-invalid y describe el error cuando existe', () => {
    render(<Input label="Contraseña" error="La contraseña es muy corta" />);

    const input = screen.getByLabelText('Contraseña');
    expect(input).toHaveAttribute('aria-invalid', 'true');

    const errorId = input.getAttribute('aria-describedby');
    expect(errorId).toBeTruthy();
    expect(document.getElementById(errorId as string)).toHaveTextContent(
      'La contraseña es muy corta'
    );
  });

  it('anuncia el error con role="alert"', () => {
    render(<Input label="Correo" error="Ingrese un correo válido" />);

    expect(screen.getByRole('alert')).toHaveTextContent('Ingrese un correo válido');
  });

  it('no marca aria-invalid ni aria-describedby cuando no hay error', () => {
    render(<Input label="Nombre" />);

    const input = screen.getByLabelText('Nombre');
    expect(input).not.toHaveAttribute('aria-invalid');
    expect(input).not.toHaveAttribute('aria-describedby');
  });

  it('describe el campo con la ayuda y conserva las descripciones externas', () => {
    render(
      <Input
        label="Teléfono"
        hint="Solo números, sin +56"
        error="Ingrese un teléfono válido"
        aria-describedby="ayuda-externa"
      />
    );

    const input = screen.getByLabelText('Teléfono');
    const ids = (input.getAttribute('aria-describedby') ?? '').split(' ');

    expect(ids).toContain('ayuda-externa');
    expect(ids).toHaveLength(3);
    expect(document.getElementById(ids[1])).toHaveTextContent('Solo números, sin +56');
    expect(document.getElementById(ids[2])).toHaveTextContent('Ingrese un teléfono válido');
  });

  it('usa la ayuda como descripción sin marcar el campo como inválido', () => {
    render(<Input label="RUT" hint="Sin puntos ni guion" />);

    const input = screen.getByLabelText('RUT');
    expect(input).not.toHaveAttribute('aria-invalid');

    const hintId = input.getAttribute('aria-describedby');
    expect(hintId).toBeTruthy();
    expect(document.getElementById(hintId as string)).toHaveTextContent('Sin puntos ni guion');
  });

  it('expone required y aria-required cuando el campo es obligatorio', () => {
    render(<Input label="Patente" required />);

    const input = screen.getByLabelText('Patente');
    expect(input).toBeRequired();
    expect(input).toHaveAttribute('aria-required', 'true');
  });
});