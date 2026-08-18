import {
  ArrowRightLeft,
  Briefcase,
  ClipboardList,
  CreditCard,
  Gauge,
  Handshake,
  Landmark,
  LayoutDashboard,
  PiggyBank,
  Repeat,
  Settings,
  Target,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react"

import type { LucideIcon } from "lucide-react"

export type NavItem = {
  title: string
  /** Caminho da rota-cliente (português, espelha o domínio). */
  url: string
  icon: LucideIcon
  /** Linha de apoio nas listas que mostram descrição (drawer "Mais" do mobile). */
  descricao?: string
}

/** Rota `url` ativa para `pathname` (o item raiz só casa exato). */
export function isActivePath(pathname: string, url: string): boolean {
  if (url === "/") {
    return pathname === "/"
  }
  return pathname === url || pathname.startsWith(`${url}/`)
}

/** Seção colapsável da navegação: ícone (visível mesmo colapsada) + itens filhos. */
export type NavSection = {
  label: string
  icon: LucideIcon
  items: NavItem[]
}

/** Item único no topo, fora das seções colapsáveis. */
export const dashboardItem: NavItem = {
  title: "Dashboard",
  url: "/",
  icon: LayoutDashboard,
}

/**
 * Investimentos é um módulo próprio, renderizado como seção colapsável entre Planejamento e
 * Compartilhado. `/investimentos` redireciona para a Visão Geral (ver router.tsx).
 */
export const investimentosSection: NavSection = {
  label: "Investimentos",
  icon: TrendingUp,
  items: [
    { title: "Visão Geral", url: "/investimentos/visao_geral", icon: Gauge },
    { title: "Carteira", url: "/investimentos/carteira", icon: Briefcase },
  ],
}

/**
 * Arquitetura de informação da navegação principal (decisão: esqueleto com IA completa); as telas
 * de cada seção entram nas fases correspondentes. Rende no padrão sidebar-08 (seções colapsáveis).
 */
export const navSections: NavSection[] = [
  {
    label: "Movimentações",
    icon: Wallet,
    items: [
      { title: "Transações", url: "/transacoes", icon: ArrowRightLeft },
      { title: "Contas", url: "/contas", icon: Landmark },
      { title: "Faturas", url: "/faturas", icon: CreditCard },
    ],
  },
  {
    label: "Planejamento",
    icon: ClipboardList,
    items: [
      { title: "Orçamentos", url: "/orcamentos", icon: PiggyBank },
      { title: "Objetivos", url: "/objetivos", icon: Target },
      { title: "Assinaturas", url: "/assinaturas", icon: Repeat },
    ],
  },
  {
    label: "Compartilhado",
    icon: Handshake,
    items: [
      {
        title: "Divisão de contas",
        url: "/divisoes",
        icon: Users,
        descricao: "Rateio entre participantes",
      },
    ],
  },
]

/** Fica no rodapé da navegação, separado das seções de domínio. */
export const settingsItem: NavItem = {
  title: "Configurações",
  url: "/configuracoes",
  icon: Settings,
  descricao: "Preferências do app",
}

/**
 * Navegação de uma conta `tipo="divisao"` (§4.11): só enxerga o módulo que justifica a conta
 * existir. Dashboard e Investimentos somem à parte (ver `app-sidebar.tsx`); Configurações
 * continua no rodapé para os dois tipos.
 */
export const navSectionsDivisaoOnly: NavSection[] = [
  {
    label: "Compartilhado",
    icon: Handshake,
    items: [
      {
        title: "Divisão de contas",
        url: "/divisoes",
        icon: Users,
        descricao: "Rateio entre participantes",
      },
    ],
  },
]

/** Aba da bottom bar do mobile: rótulo curto para caber em 360px + rotas irmãs que a acendem. */
export type BottomNavItem = NavItem & {
  short: string
  /** Prefixos extras que também deixam a aba ativa (ex.: Contas/Faturas em "Movimentações"). */
  match?: string[]
}

/**
 * Abas fixas da navegação inferior no mobile (`< md`). São os destinos de uso diário; o resto da
 * IA fica na aba "Mais" (ver `bottom-nav.tsx`), que é derivada de `navSections` — item novo numa
 * seção aparece lá sozinho, sem tocar aqui.
 */
export const bottomNavItems: BottomNavItem[] = [
  { ...dashboardItem, short: "Dashboard" },
  {
    title: "Transações",
    short: "Movimentações",
    url: "/transacoes",
    icon: ArrowRightLeft,
    match: ["/contas", "/faturas"],
  },
  {
    title: "Orçamentos",
    short: "Orçamento",
    url: "/orcamentos",
    icon: PiggyBank,
  },
  {
    title: "Divisão de contas",
    short: "Divisão",
    url: "/divisoes",
    icon: Users,
  },
]

/** Conta `tipo="divisao"`: sobra só o módulo dela — o resto vive na aba "Mais". */
export const bottomNavItemsDivisaoOnly: BottomNavItem[] = [
  {
    title: "Divisão de contas",
    short: "Divisão",
    url: "/divisoes",
    icon: Users,
  },
]

/** Aba ativa considerando os prefixos irmãos declarados em `match`. */
export function isBottomNavItemActive(
  pathname: string,
  item: BottomNavItem
): boolean {
  return [item.url, ...(item.match ?? [])].some((url) =>
    isActivePath(pathname, url)
  )
}
