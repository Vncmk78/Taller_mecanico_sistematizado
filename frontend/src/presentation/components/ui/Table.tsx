import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react';

interface TableProps {
  className?: string;
  children: ReactNode;
}

export function Table({ className = '', children }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table className={`w-full border-collapse ${className}`}>{children}</table>
    </div>
  );
}

interface TableHeadProps {
  className?: string;
  children: ReactNode;
}

export function TableHead({ className = '', children }: TableHeadProps) {
  return (
    <thead className={`bg-bg-secondary ${className}`}>
      {children}
    </thead>
  );
}

interface TableBodyProps {
  className?: string;
  children: ReactNode;
}

export function TableBody({ className = '', children }: TableBodyProps) {
  return <tbody className={className}>{children}</tbody>;
}

interface TableRowProps {
  className?: string;
  children: ReactNode;
  onClick?: () => void;
}

export function TableRow({ className = '', children, onClick }: TableRowProps) {
  return (
    <tr
      onClick={onClick}
      className={`border-b border-border-custom hover:bg-bg-secondary/50 transition-colors ${onClick ? 'cursor-pointer' : ''} ${className}`}
    >
      {children}
    </tr>
  );
}

interface TableHeaderCellProps extends ThHTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
}

export function TableHeaderCell({ className = '', children, ...props }: TableHeaderCellProps) {
  return (
    <th
      className={`text-left p-4 text-xs font-semibold text-text-muted uppercase tracking-wider ${className}`}
      {...props}
    >
      {children}
    </th>
  );
}

interface TableCellProps extends TdHTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
}

export function TableCell({ className = '', children, ...props }: TableCellProps) {
  return (
    <td className={`p-4 text-sm text-text-main ${className}`} {...props}>
      {children}
    </td>
  );
}

export function TableEmptyState({ message = 'Sin resultados', colSpan = 1 }: { message?: string; colSpan?: number }) {
  return (
    <tr>
      <td colSpan={colSpan} className="text-center py-8 text-text-muted">
        {message}
      </td>
    </tr>
  );
}
