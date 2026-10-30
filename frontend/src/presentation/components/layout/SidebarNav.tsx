import { AppBrand } from '@/presentation/components/layout/AppBrand';
import { AppNavLink, type NavSection } from '@/presentation/components/layout/AppNavLink';

interface SidebarNavProps {
  sections: NavSection[];
}

export function SidebarNav({ sections }: SidebarNavProps) {
  return (
    <aside
      aria-label="Menú lateral"
      className="w-[280px] bg-primary-blue border-r border-[#0B1017] flex flex-col z-10 shrink-0"
    >
      <div className="flex items-center gap-2.5 p-7 border-b border-white/10">
        <AppBrand />
      </div>

      <nav aria-label="Navegación de sesión" className="flex flex-col gap-2 p-5 flex-grow overflow-y-auto">
        {sections.map((section, indice) => (
          <div key={section.title ?? `seccion-${indice}`} className="flex flex-col">
            {section.title && (
              <div className="text-xs text-[#64748B] uppercase font-bold tracking-[1.5px] mx-4 mt-4 mb-2">
                {section.title}
              </div>
            )}
            {section.items.map((item) => (
              <AppNavLink key={item.to} variant="sidebar" {...item} />
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}