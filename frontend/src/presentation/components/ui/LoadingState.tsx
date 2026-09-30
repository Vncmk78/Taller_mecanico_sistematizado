import { Spinner } from '@/presentation/components/ui/Spinner';

interface LoadingStateProps {
    message: string;
    className?: string;
}

export function LoadingState({ message, className = '' }: LoadingStateProps) {
    return (
        <div className={`flex items-center gap-3 text-text-muted ${className}`}>
            <Spinner label={message} />
            <span>{message}</span>
        </div>
    );
}