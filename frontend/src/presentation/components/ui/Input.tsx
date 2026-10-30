import type { InputHTMLAttributes, ReactNode } from 'react';
import { forwardRef, useId } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: ReactNode;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      icon,
      error,
      hint,
      className = '',
      required,
      'aria-describedby': ariaDescribedBy,
      'aria-invalid': ariaInvalid,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const inputId = props.id ?? generatedId;
    const hintId = hint ? `${inputId}-hint` : undefined;
    const errorId = error ? `${inputId}-error` : undefined;
    // Se conserva cualquier descripción que pase el consumidor y se añaden la
    // ayuda y el error del propio campo, sin pisar unos con otros.
    const describedBy =
      [ariaDescribedBy, hintId, errorId].filter(Boolean).join(' ') || undefined;

    return (
      <div className="mb-6">
        {label && (
          <label htmlFor={inputId} className="block mb-2 text-sm text-text-muted">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {icon && (
            <span aria-hidden className="absolute left-4 text-text-muted text-lg">
              {icon}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            required={required}
            aria-required={required ? true : undefined}
            aria-invalid={ariaInvalid ?? (error ? true : undefined)}
            aria-describedby={describedBy}
            className={`w-full py-3.5 pr-4 bg-surface border rounded-lg text-text-main text-base transition-all duration-300 outline-none focus:border-primary-blue focus:bg-surface focus:shadow-[0_0_0_3px_rgba(21,40,63,0.15)] ${
              icon ? 'pl-12' : 'pl-4'
            } ${error ? 'border-status-red' : 'border-border-custom'} ${className}`}
            {...props}
          />
        </div>
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

Input.displayName = 'Input';
