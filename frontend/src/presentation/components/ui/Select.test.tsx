import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Select } from '@/presentation/components/ui/Select';

describe('Select: selector de formulario accesible', () => {
  it('asocia el label con el select mediante id generado', () => {
    render(
      <Select label="Tipo">
        <option value="a">Opción A</option>
      </Select>
    );

    expect(screen.getByLabelText('Tipo')).toBeInTheDocument();
  });

  it('marca aria-invalid y describe el error cuando existe', () => {
    render(
      <Select label="Proveedor" error="Seleccione un proveedor">
        <option value="">Seleccionar...</option>
      </Select>
    );

    const select = screen.getByLabelText('Proveedor');
    expect(select).toHaveAttribute('aria-invalid', 'true');

    const errorId = select.getAttribute('aria-describedby');
    expect(errorId).toBeTruthy();
    expect(document.getElementById(errorId as string)).toHaveTextContent(
      'Seleccione un proveedor'
    );
  });

  it('anuncia el error con role="alert"', () => {
    render(
      <Select label="Tipo" error="Seleccione un tipo">
        <option value="">Seleccionar...</option>
      </Select>
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Seleccione un tipo');
  });

  it('conserva las descripciones externas y las combina con ayuda y error', () => {
    render(
      <Select
        label="Contexto"
        hint="Elige el contexto de la evidencia"
        error="Contexto inválido"
        aria-describedby="ayuda-externa"
      >
        <option value="diagnostico">Diagnóstico</option>
      </Select>
    );

    const select = screen.getByLabelText('Contexto');
    const ids = (select.getAttribute('aria-describedby') ?? '').split(' ');

    expect(ids).toContain('ayuda-externa');
    expect(ids).toHaveLength(3);
    expect(document.getElementById(ids[1])).toHaveTextContent(
      'Elige el contexto de la evidencia'
    );
    expect(document.getElementById(ids[2])).toHaveTextContent('Contexto inválido');
  });

  it('expone required y aria-required cuando el campo es obligatorio', () => {
    render(
      <Select label="Proveedor" required>
        <option value="">Seleccionar...</option>
      </Select>
    );

    const select = screen.getByLabelText('Proveedor');
    expect(select).toBeRequired();
    expect(select).toHaveAttribute('aria-required', 'true');
  });

  it('permite usar aria-label sin label visible', () => {
    render(
      <Select aria-label="Filtrar por estado" value="all" onChange={() => undefined}>
        <option value="all">Todos</option>
      </Select>
    );

    const select = screen.getByLabelText('Filtrar por estado');
    fireEvent.change(select, { target: { value: 'all' } });
    expect(select).toHaveValue('all');
  });

  it('propaga el evento onChange', () => {
    const onChange = vi.fn();
    render(
      <Select label="Tipo" onChange={onChange}>
        <option value="a">A</option>
        <option value="b">B</option>
      </Select>
    );

    fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'b' } });
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});
