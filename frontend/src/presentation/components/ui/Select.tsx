import type { ReactNode, SelectHTMLAttributes } from 'react';
import { forwardRef, useId } from 'react';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  containerClassName?: string;
  children: ReactNode;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      error,
      hint,
      containerClassName = 'mb-6',
      className = '',
      required,
      children,
      'aria-describedby': ariaDescribedBy,
      'aria-invalid': ariaInvalid,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const selectId = props.id ?? generatedId;
    const hintId = hint ? `${selectId}-hint` : undefined;
    const errorId = error ? `${selectId}-error` : undefined;
    const describedBy =
      [ariaDescribedBy, hintId, errorId].filter(Boolean).join(' ') || undefined;

    return (
      <div className={containerClassName}>
        {label && (
          <label htmlFor={selectId} className="block mb-2 text-sm text-text-muted">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          required={required}
          aria-required={required ? true : undefined}
          aria-invalid={ariaInvalid ?? (error ? true : undefined)}
          aria-describedby={describedBy}
          className={`w-full py-3.5 pr-10 pl-4 bg-surface border rounded-lg text-text-main text-base transition-all duration-300 outline-none focus:border-primary-blue focus:bg-surface focus:shadow-[0_0_0_3px_rgba(21,40,63,0.15)] ${
            error ? 'border-status-red' : 'border-border-custom'
          } ${className}`}
          {...props}
        >
          {children}
        </select>
        {hint && (
          <p id={hintId} className="mt-1 text-sm text-text-muted">
            {hint}
          </p>
        )}
        {error && (
          <p id={errorId} role="alert" className="mt-1 text-sm text-status-red">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Select.displayName = 'Select';
