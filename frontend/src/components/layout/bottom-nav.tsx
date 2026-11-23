import { createPortal } from "react-dom"
import { NavLink, useLocation } from "react-router"

import {
  atalhosEfetivos,
  bottomNavItemsDivisaoOnly,
  inicioItem,
  isBottomNavItemActive,
  type BottomNavItem,
} from "@/config/nav"
import { useMe } from "@/lib/api/auth"
import { usePerfil } from "@/lib/api/perfil"
import { cn } from "@/lib/utils"

function Aba({ item, pathname }: { item: BottomNavItem; pathname: string }) {
  const ativa = isBottomNavItemActive(pathname, item)
  return (
    <li className="flex min-w-0 flex-1">
      <NavLink
        to={item.url}
        aria-current={ativa ? "page" : undefined}
        className={cn(
          "flex w-full min-w-0 flex-col items-center justify-center gap-1 rounded-3xl transition-colors duration-150 motion-reduce:transition-none",
          ativa ? "font-medium text-accent-ink" : "text-muted-foreground"
        )}
      >
        <item.icon className="size-6" aria-hidden />
        <span className="max-w-full truncate text-[11px] leading-none">
          {item.short}
        </span>
      </NavLink>
    </li>
  )
}

/**
 * Barra de atalhos do mobile (`< md`): pílula flutuante com "Início" fixo + 3 atalhos escolhidos
 * em Configurações → Preferências (`perfil.atalhos_mobile`). A navegação completa fica no menu
 * lateral (☰ da topbar). Escondida por CSS, não por `useIsMobile()` — o hook começa `false` e
 * piscaria a barra no primeiro paint do desktop.
 *
 * Vai num portal para o `body`, como todo `fixed` do shadcn aqui (sheet, dialog, drawer): dentro
 * do `SidebarInset` bastaria um ancestral ganhar `transform`/`filter`/`backdrop-filter` para virar
 * o containing block e a barra passar a rolar com o conteúdo em vez de ficar presa à viewport.
 */
export function BottomNav() {
  const { pathname } = useLocation()
  const me = useMe()
  const perfil = usePerfil()
  const abas =
    me.data?.tipo === "divisao"
      ? bottomNavItemsDivisaoOnly
      : [inicioItem, ...atalhosEfetivos(perfil.data?.atalhos_mobile)]

  return createPortal(
    <nav
      aria-label="Atalhos"
      className="fixed inset-x-4 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] z-40 md:hidden"
    >
      {/* Sombra bem leve na cor de destaque (o accent do usuário) + 1px neutro para assentar. */}
      <ul className="mx-auto flex h-(--bottom-nav-h) max-w-md items-stretch rounded-[1.75rem] border border-border/60 bg-background/95 px-1 shadow-[0_10px_30px_-10px_color-mix(in_oklch,var(--primary)_35%,transparent),0_1px_2px_rgb(0_0_0/0.04)] backdrop-blur-md">
        {abas.map((item) => (
          <Aba key={item.url} item={item} pathname={pathname} />
        ))}
      </ul>
    </nav>,
    document.body
  )
}
