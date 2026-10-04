import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { Toast, type ToastMessage, type ToastTone } from '@/presentation/components/ui/Toast';
import { ToastContext, type ToastContextValue } from '@/presentation/components/ui/toastContext';

let nextToastId = 0;

/**
 * Cola de avisos flotantes compartida por los tres portales. Se monta en App.tsx
 * para que cualquier vista pueda confirmar una acción sin cablear props.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<ToastMessage[]>([]);

    const dismiss = useCallback((id: number) => {
        setToasts((current) => current.filter((toast) => toast.id !== id));
    }, []);

    const showToast = useCallback((text: string, tone: ToastTone = 'info') => {
        setToasts((current) => [...current, { id: nextToastId++, tone, text }]);
    }, []);

    const value = useMemo<ToastContextValue>(() => ({ showToast }), [showToast]);

    return (
        <ToastContext.Provider value={value}>
            {children}
            <div className="fixed bottom-6 right-6 z-[60] flex flex-col gap-3 items-end">
                {toasts.map((toast) => (
                    <Toast key={toast.id} toast={toast} onDismiss={dismiss} />
                ))}
            </div>
        </ToastContext.Provider>
    );
}