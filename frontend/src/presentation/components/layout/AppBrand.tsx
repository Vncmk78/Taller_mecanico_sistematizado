import { Settings, Wrench } from 'lucide-react';

export function AppBrand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="relative inline-block w-[35px] h-[35px] text-gray-400">
        <Settings className="absolute left-0 top-0 w-6 h-6" />
        <Wrench className="absolute left-3 top-3 w-4 h-4 text-primary-red -rotate-15" />
      </span>
      <div className="text-sm leading-tight font-bold">
        Sistema<br />Mecánico
      </div>
    </div>
  );
}