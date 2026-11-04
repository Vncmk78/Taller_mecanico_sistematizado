import type { TextareaHTMLAttributes } from 'react';
import { forwardRef, useId } from 'react';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
  containerClassName?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      error,
      hint,
      containerClassName = 'mb-6',
      className = '',
      required,
      'aria-describedby': ariaDescribedBy,
      'aria-invalid': ariaInvalid,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const textareaId = props.id ?? generatedId;
    const hintId = hint ? `${textareaId}-hint` : undefined;
    const errorId = error ? `${textareaId}-error` : undefined;
    const describedBy =
      [ariaDescribedBy, hintId, errorId].filter(Boolean).join(' ') || undefined;

    return (
      <div className={containerClassName}>
        {label && (
          <label htmlFor={textareaId} className="block mb-2 text-sm text-text-muted">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          required={required}
          aria-required={required ? true : undefined}
          aria-invalid={ariaInvalid ?? (error ? true : undefined)}
          aria-describedby={describedBy}
          className={`w-full py-3.5 px-4 bg-surface border rounded-lg text-text-main text-base transition-all duration-300 outline-none resize-y focus:border-primary-blue focus:bg-surface focus:shadow-[0_0_0_3px_rgba(21,40,63,0.15)] ${
            error ? 'border-status-red' : 'border-border-custom'
          } ${className}`}
          {...props}
        />
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

Textarea.displayName = 'Textarea';
