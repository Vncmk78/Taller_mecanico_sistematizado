import type { ReactNode } from 'react';

interface FormActionsProps {
  children: ReactNode;
  className?: string;
}

/** Fila de acciones al pie de un formulario (cancelar + confirmar). */
export function FormActions({ children, className = '' }: FormActionsProps) {
  return <div className={`flex justify-end gap-3 ${className}`}>{children}</div>;
}
