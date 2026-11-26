import { createPortal } from "react-dom"
import { NavLink, useLocation } from "react-router"

import {
  atalhosEfetivos,
  bottomNavItemsDivisaoOnly,
  inicioBottomItem,
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
        title={item.title}
        className={cn(
          "flex w-full min-w-0 flex-col items-center justify-center gap-1 rounded-full transition-[background-color,color,transform] duration-200 ease-(--ease-out) active:scale-95 motion-reduce:transition-none motion-reduce:active:scale-100",
          ativa
            ? "bg-marca-forte font-bold text-primary-foreground"
            : "font-medium text-muted-foreground"
        )}
      >
        <item.icon className="size-6" aria-hidden />
        <span className="sr-only">{item.title}</span>
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
      : [inicioBottomItem, ...atalhosEfetivos(perfil.data?.atalhos_mobile)]

  return createPortal(
    <nav
      aria-label="Atalhos"
      className="fixed inset-x-4 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] z-40 md:hidden"
    >
      {/* Só ícones (Nubank), barra flutuante quase opaca — uma transparência levíssima —, com
          sombra; a aba ativa numa pílula na cor forte do accent. O nome de cada aba fica para
          leitor de tela e no `title`. */}
      <ul className="mx-auto flex h-(--bottom-nav-h) max-w-md items-stretch gap-1 rounded-full bg-background/93 p-1.5 shadow-(--shadow-pop) ring-1 ring-foreground/5 backdrop-blur-md">
        {abas.map((item) => (
          <Aba key={item.url} item={item} pathname={pathname} />
        ))}
      </ul>
    </nav>,
    document.body
  )
}
