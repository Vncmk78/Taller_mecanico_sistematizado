import { createContext, useContext } from 'react';
import type { ToastTone } from '@/presentation/components/ui/Toast';

export interface ToastContextValue {
    showToast: (text: string, tone?: ToastTone) => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast debe usarse dentro de un ToastProvider');
    }
    return context;
}