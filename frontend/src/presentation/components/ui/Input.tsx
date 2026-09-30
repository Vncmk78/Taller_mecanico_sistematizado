import type { InputHTMLAttributes, ReactNode } from 'react';
import { forwardRef, useId } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: ReactNode;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, icon, error, className = '', ...props }, ref) => {
    const generatedId = useId();
    const inputId = props.id ?? generatedId;
    const errorId = error ? `${inputId}-error` : undefined;
    return (
      <div className="mb-6">
        {label && (
          <label htmlFor={inputId} className="block mb-2 text-sm text-text-muted">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {icon && (
            <span className="absolute left-4 text-text-muted text-lg">
              {icon}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            aria-invalid={error ? true : undefined}
            aria-describedby={errorId}
            className={`w-full py-3.5 pr-4 bg-surface border rounded-lg text-text-main text-base transition-all duration-300 outline-none focus:border-primary-blue focus:bg-surface focus:shadow-[0_0_0_3px_rgba(21,40,63,0.15)] ${
              icon ? 'pl-12' : 'pl-4'
            } ${error ? 'border-status-red' : 'border-border-custom'} ${className}`}
            {...props}
          />
        </div>
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
