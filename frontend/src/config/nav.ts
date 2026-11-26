import {
  ArrowRightLeft,
  Briefcase,
  CalendarCheck,
  ClipboardList,
  CreditCard,
  Gauge,
  Handshake,
  House,
  Landmark,
  LayoutDashboard,
  MessageSquareText,
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
  /** Linha de apoio (hoje só "Divisão de contas" e "Configurações" usam). */
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

/** Itens únicos no topo, fora das seções colapsáveis: o Início (hub) e o Dashboard (análises). */
export const inicioItem: NavItem = {
  title: "Início",
  url: "/",
  icon: House,
}

export const dashboardItem: NavItem = {
  title: "Dashboard",
  url: "/dashboard",
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
      { title: "Despesas fixas", url: "/despesas-fixas", icon: CalendarCheck },
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

/** 1ª aba da barra inferior, fixa (as outras 3 o usuário escolhe). */
export const inicioBottomItem: BottomNavItem = {
  ...inicioItem,
  short: "Início",
}

export type Atalho = BottomNavItem & { id: string }

/**
 * Destinos que podem ocupar as 3 abas configuráveis da barra inferior (Configurações →
 * Preferências). O `id` é o que vai para `perfil.atalhos_mobile`; id que sair daqui é ignorado.
 */
export const ATALHOS: Atalho[] = [
  {
    id: "transacoes",
    title: "Transações",
    short: "Transações",
    url: "/transacoes",
    icon: ArrowRightLeft,
  },
  {
    id: "contas",
    title: "Contas",
    short: "Contas",
    url: "/contas",
    icon: Landmark,
  },
  {
    id: "faturas",
    title: "Faturas",
    short: "Faturas",
    url: "/faturas",
    icon: CreditCard,
  },
  {
    id: "orcamentos",
    title: "Orçamentos",
    short: "Orçamento",
    url: "/orcamentos",
    icon: PiggyBank,
  },
  {
    id: "objetivos",
    title: "Objetivos",
    short: "Objetivos",
    url: "/objetivos",
    icon: Target,
  },
  {
    id: "assinaturas",
    title: "Assinaturas",
    short: "Assinaturas",
    url: "/assinaturas",
    icon: Repeat,
  },
  {
    id: "despesas-fixas",
    title: "Despesas fixas",
    short: "Fixas",
    url: "/despesas-fixas",
    icon: CalendarCheck,
  },
  {
    id: "investimentos",
    title: "Investimentos",
    short: "Investimentos",
    url: "/investimentos/visao_geral",
    icon: TrendingUp,
    match: ["/investimentos"],
  },
  {
    id: "divisoes",
    title: "Divisão de contas",
    short: "Divisão",
    url: "/divisoes",
    icon: Users,
  },
  { ...dashboardItem, id: "dashboard", short: "Dashboard" },
  {
    id: "chat",
    title: "Assistente",
    short: "Assistente",
    url: "/chat",
    icon: MessageSquareText,
  },
  { ...settingsItem, id: "configuracoes", short: "Configurações" },
]

export const ATALHOS_PADRAO = ["transacoes", "orcamentos", "investimentos"]

/**
 * Os 3 atalhos em vigor: os salvos que o catálogo conhece, sem repetir, completados com os
 * padrões (lista salva curta, ou com id que saiu do catálogo, ainda dá 3 abas).
 */
export function atalhosEfetivos(salvos: string[] | null | undefined): Atalho[] {
  const ids: string[] = []
  for (const id of [
    ...(salvos ?? []),
    ...ATALHOS_PADRAO,
    ...ATALHOS.map((a) => a.id),
  ])
    if (!ids.includes(id) && ATALHOS.some((a) => a.id === id)) ids.push(id)
  return ids.slice(0, 3).map((id) => ATALHOS.find((a) => a.id === id)!)
}

/** Conta `tipo="divisao"`: barra fixa com o módulo dela e as configurações (sem escolha). */
export const bottomNavItemsDivisaoOnly: BottomNavItem[] = [
  {
    title: "Divisão de contas",
    short: "Divisão",
    url: "/divisoes",
    icon: Users,
  },
  { ...settingsItem, short: "Configurações" },
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
