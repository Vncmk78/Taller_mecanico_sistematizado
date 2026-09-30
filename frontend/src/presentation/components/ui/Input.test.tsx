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
});