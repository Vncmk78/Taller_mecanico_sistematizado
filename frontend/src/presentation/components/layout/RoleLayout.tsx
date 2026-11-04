import { useEffect, useState, type ReactNode } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { AppBrand } from '@/presentation/components/layout/AppBrand';
import { AppNavLink, type NavSection } from '@/presentation/components/layout/AppNavLink';
import { SidebarNav } from '@/presentation/components/layout/SidebarNav';
import { TopBar } from '@/presentation/components/layout/TopBar';
import { UserMenu } from '@/presentation/components/layout/UserMenu';

export interface RoleLayoutProps {
  variant: 'sidebar' | 'topnav';
  sections: NavSection[];
  badge?: string;
  userName: string;
  userSubtitle: string;
  onLogout: () => void;
  headerLeft?: ReactNode;
  headerRightPrepend?: ReactNode;
}

export function RoleLayout({
  variant,
  sections,
  badge,
  userName,
  userSubtitle,
  onLogout,
  headerLeft,
  headerRightPrepend,
}: RoleLayoutProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  if (variant === 'topnav') {
    return (
      <div className="min-h-screen flex flex-col animate-fade-in">
        <a
          href="#contenido-principal"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-text-main"
        >
          Saltar al contenido principal
        </a>
        <header className="flex items-center justify-between gap-2 px-4 sm:px-6 lg:px-10 py-4 border-b-3 border-b-primary-orange bg-[#111318] sticky top-0 z-50 text-white shadow-[0_4px_14px_rgba(0,0,0,0.25)]">
          <div className="flex items-center gap-2.5 shrink-0">
            <AppBrand />
            {badge && (
              <span className="hidden sm:inline-flex ml-3 text-xs bg-primary-blue/15 text-primary-blue px-3 py-1 rounded-full border border-primary-blue/40 font-bold">
                {badge}
              </span>
            )}
          </div>

          <nav
            aria-label="Navegación principal"
            className="flex items-center gap-1 sm:gap-2 min-w-0 flex-1 justify-start xl:justify-center overflow-x-auto"
          >
            {sections.flatMap((section) => section.items).map((item) => (
              <AppNavLink key={item.to} variant="topnav" {...item} />
            ))}
          </nav>

          <div className="shrink-0">
            <UserMenu
              userName={userName}
              subtitle={userSubtitle}
              onLogout={onLogout}
            />
          </div>
        </header>

        <main id="contenido-principal" tabIndex={-1} className="flex-grow focus:outline-none">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <a
        href="#contenido-principal"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-text-main"
      >
        Saltar al contenido principal
      </a>

      {/* Sidebar de escritorio */}
      <div className="hidden lg:block">
        <SidebarNav sections={sections} />
      </div>

      {/* Botón hamburguesa móvil */}
      <button
        type="button"
        aria-label={mobileMenuOpen ? 'Cerrar menú' : 'Abrir menú'}
        aria-expanded={mobileMenuOpen}
        aria-controls="menu-movil-sidebar"
        onClick={() => setMobileMenuOpen((v) => !v)}
        className="lg:hidden fixed top-3 left-3 z-[60] inline-flex items-center justify-center w-11 h-11 rounded-lg bg-primary-blue text-white shadow-lg border border-white/10"
      >
        {mobileMenuOpen ? <X className="w-5 h-5" aria-hidden /> : <Menu className="w-5 h-5" aria-hidden />}
      </button>

      {/* Drawer móvil */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden
          />
          <div
            id="menu-movil-sidebar"
            className="relative z-10 h-full shadow-xl animate-fade-in"
          >
            <SidebarNav sections={sections} />
          </div>
        </div>
      )}

      <main
        id="contenido-principal"
        tabIndex={-1}
        className="flex-grow flex flex-col bg-bg-secondary min-h-screen lg:h-screen lg:overflow-y-auto focus:outline-none pt-14 lg:pt-0"
      >
        <TopBar
          left={headerLeft}
          rightPrepend={headerRightPrepend}
          badge={badge}
          userName={userName}
          userSubtitle={userSubtitle}
          onLogout={onLogout}
        />

        <div className="flex-grow">
          <Outlet />
        </div>
      </main>
    </div>
  );
}