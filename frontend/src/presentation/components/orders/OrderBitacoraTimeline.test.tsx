import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { BitacoraEntry } from '@/domain/entities/Bitacora';
import { OrderBitacoraTimeline } from './OrderBitacoraTimeline';

const accion: BitacoraEntry = {
    id: '77',
    ordenId: '31',
    autorUsuarioId: '50',
    tipo: 'accion',
    descripcion: 'Se reemplazaron las pastillas delanteras',
    creadoEn: '2026-09-28T12:15:00-03:00',
    repuestos: [{ nombre: 'Pastillas de freno', cantidad: 2 }],
};

const observacion: BitacoraEntry = {
    id: '78',
    ordenId: '31',
    autorUsuarioId: '50',
    tipo: 'observacion',
    descripcion: 'El cliente reporta ruido al frenar',
    creadoEn: '2026-09-28T13:00:00-03:00',
    repuestos: [],
};

describe('OrderBitacoraTimeline', () => {
    it('muestra la etiqueta del tipo, la descripción y los repuestos de una acción', () => {
        render(<OrderBitacoraTimeline entries={[accion]} loading={false} />);

        expect(screen.getByText('Acción')).toBeInTheDocument();
        expect(screen.getByText('Se reemplazaron las pastillas delanteras')).toBeInTheDocument();
        expect(screen.getByText('Pastillas de freno × 2')).toBeInTheDocument();
        expect(screen.getByText('Usuario 50')).toBeInTheDocument();
    });

    it('no lista repuestos en una observación', () => {
        render(<OrderBitacoraTimeline entries={[observacion]} loading={false} />);

        expect(screen.getByText('Observación')).toBeInTheDocument();
        expect(screen.queryByText(/×/)).not.toBeInTheDocument();
    });

    it('muestra el esqueleto de carga', () => {
        render(<OrderBitacoraTimeline entries={[]} loading />);

        expect(screen.getByLabelText('Cargando bitácora')).toBeInTheDocument();
    });

    it('muestra el estado vacío cuando no hay entradas', () => {
        render(<OrderBitacoraTimeline entries={[]} loading={false} />);

        expect(screen.getByText('Sin entradas en la bitácora.')).toBeInTheDocument();
    });

    it('distingue el fallo de carga del estado vacío', () => {
        render(<OrderBitacoraTimeline entries={[]} loading={false} failed />);

        expect(screen.getByText('No se pudo cargar la bitácora de trabajo.')).toBeInTheDocument();
        expect(screen.queryByText('Sin entradas en la bitácora.')).not.toBeInTheDocument();
    });
});
