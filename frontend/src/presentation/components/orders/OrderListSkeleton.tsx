interface OrderListSkeletonProps {
    count?: number;
    className?: string;
}

export function OrderListSkeleton({ count = 6, className = '' }: OrderListSkeletonProps) {
    return (
        <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 ${className}`}>
            {Array.from({ length: count }).map((_, i) => (
                <div key={i} className="card p-5 animate-pulse space-y-3">
                    <div className="flex justify-between items-center">
                        <div className="h-5 bg-bg-secondary rounded w-1/3" />
                        <div className="h-5 bg-bg-secondary rounded w-20" />
                    </div>
                    <div className="h-5 bg-bg-secondary rounded w-2/3" />
                    <div className="h-4 bg-bg-secondary rounded w-1/2" />
                    <div className="h-9 bg-bg-secondary rounded mt-4" />
                </div>
            ))}
        </div>
    );
}