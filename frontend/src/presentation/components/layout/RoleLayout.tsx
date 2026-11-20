import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AppBrand } from '@/presentation/components/layout/AppBrand';
import { AppNavLink, type NavSection } from '@/presentation/components/layout/AppNavLink';
import { NotificationBell } from '@/presentation/components/notifications/NotificationBell';
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
  const { pathname } = useLocation();
  // Se guarda la ruta en la que se abrió el menú, no un booleano: al cambiar de
  // ruta (atras/adelante o navegación programática) `menuOpen` pasa a false por
  // derivación, sin un efecto que fuerce un render adicional.
  const [menuPath, setMenuPath] = useState<string | null>(null);
  const menuOpen = menuPath === pathname;

  const cerrarMenu = useCallback(() => setMenuPath(null), []);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') cerrarMenu();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [menuOpen, cerrarMenu]);

  if (variant === 'topnav') {
    return (
      <div className="min-h-[var(--viewport-height)] flex flex-col animate-fade-in">
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

          <div className="flex items-center gap-2 shrink-0">
            <NotificationBell tone="dark" />
            <UserMenu
              userName={userName}
              subtitle={userSubtitle}
              onLogout={onLogout}
              tone="dark"
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
    <div className="flex min-h-[var(--viewport-height)]">
      <a
        href="#contenido-principal"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-text-main"
      >
        Saltar al contenido principal
      </a>
      <SidebarNav sections={sections} open={menuOpen} onClose={cerrarMenu} />

      <main
        id="contenido-principal"
        tabIndex={-1}
        className="flex min-w-0 flex-grow flex-col bg-bg-secondary min-h-[var(--viewport-height)] lg:h-[var(--viewport-height)] lg:overflow-y-auto focus:outline-none"
      >
        <TopBar
          left={headerLeft}
          rightPrepend={headerRightPrepend}
          badge={badge}
          userName={userName}
          userSubtitle={userSubtitle}
          onLogout={onLogout}
          onOpenMenu={() => setMenuPath(pathname)}
          menuOpen={menuOpen}
        />

        <div className="flex-grow">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
