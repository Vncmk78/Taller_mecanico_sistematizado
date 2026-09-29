import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ESTADOS_ORDEN } from '@/domain/entities/Order';
import { OrderStatusBadge } from './OrderStatusBadge';

const casos: Array<[number, string]> = Object.entries(ESTADOS_ORDEN).map(([codigo, label]) => [
    Number(codigo),
    label,
]);

describe('OrderStatusBadge: etiquetas visuales de los estados de orden', () => {
    it.each(casos)('muestra la etiqueta del estado %i (%s)', (codigo, label) => {
        render(<OrderStatusBadge estadoCodigo={codigo} />);
        expect(screen.getByText(label)).toBeInTheDocument();
        expect(screen.getByTitle(label)).toBeInTheDocument();
    });

    it('variante pill (default): fondo tintado y borde del color del estado', () => {
        render(<OrderStatusBadge estadoCodigo={1} />);
        const pill = screen.getByText('Recibido').closest('span');
        expect(pill?.className).toContain('rounded-full');
        expect(pill?.className).toContain('bg-status-blue/15');
    });

    it('variante dot: punto de color + etiqueta sin fondo', () => {
        const { container } = render(<OrderStatusBadge estadoCodigo={6} variant="dot" />);
        const wrapper = screen.getByText('Listo');
        expect(wrapper.className).toContain('gap-1.5');
        expect(wrapper.className).not.toContain('rounded-full');
        const dot = container.querySelector('span[aria-hidden]');
        expect(dot?.className).toContain('h-2 w-2 rounded-full bg-status-green');
    });

    it('tamaños sm y md aplican clases distintas', () => {
        const { container } = render(
            <>
                <OrderStatusBadge estadoCodigo={2} />
                <OrderStatusBadge estadoCodigo={2} size="sm" />
            </>
        );
        const badges = container.querySelectorAll('span[title]');
        expect(badges[0].className).toContain('px-2.5 py-1');
        expect(badges[1].className).toContain('px-2 py-0.5');
    });
});