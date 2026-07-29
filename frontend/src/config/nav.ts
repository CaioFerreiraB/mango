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
    items: [{ title: "Divisão de contas", url: "/divisoes", icon: Users }],
  },
]

/** Fica no rodapé da navegação, separado das seções de domínio. */
export const settingsItem: NavItem = {
  title: "Configurações",
  url: "/configuracoes",
  icon: Settings,
}
