import {
  ArrowLeftRight,
  Baby,
  BookOpen,
  Briefcase,
  Bus,
  Cake,
  Camera,
  Car,
  Church,
  CircleQuestionMark,
  Coffee,
  Dice5,
  Dumbbell,
  Flower2,
  Fuel,
  Gamepad2,
  Gift,
  GraduationCap,
  Hammer,
  HeartHandshake,
  HeartPulse,
  Home,
  Landmark,
  MonitorSmartphone,
  Music,
  PawPrint,
  Percent,
  PiggyBank,
  Pill,
  Plane,
  ReceiptText,
  Scale,
  Scissors,
  Send,
  ShieldCheck,
  Shirt,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Tag,
  TrendingUp,
  UtensilsCrossed,
  Wallet,
  Wifi,
  Wrench,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useMemo } from "react"

import { useCategorias, type Categoria } from "@/lib/api/categorias"

/** Catálogo oferecido ao usuário para uma categoria própria. A chave é o que vai para o banco
 * (`categoria.icone`) e precisa casar com `app/enums.ICONE_CATEGORIA` — aquela lista valida na
 * fronteira, esta é a que de fato desenha. */
export const ICONES_DISPONIVEIS = {
  // Os 22 das raízes do Pluggy, para uma categoria própria conversar com a taxonomia.
  wallet: Wallet,
  landmark: Landmark,
  "trending-up": TrendingUp,
  "arrow-left-right": ArrowLeftRight,
  send: Send,
  scale: Scale,
  wrench: Wrench,
  "shopping-bag": ShoppingBag,
  "monitor-smartphone": MonitorSmartphone,
  "shopping-cart": ShoppingCart,
  "utensils-crossed": UtensilsCrossed,
  plane: Plane,
  "heart-handshake": HeartHandshake,
  "dice-5": Dice5,
  "receipt-text": ReceiptText,
  percent: Percent,
  home: Home,
  "heart-pulse": HeartPulse,
  car: Car,
  "shield-check": ShieldCheck,
  "gamepad-2": Gamepad2,
  tag: Tag,
  // Os que a taxonomia do banco não cobre — o motivo de existir categoria personalizada.
  "paw-print": PawPrint,
  gift: Gift,
  "graduation-cap": GraduationCap,
  baby: Baby,
  dumbbell: Dumbbell,
  coffee: Coffee,
  "book-open": BookOpen,
  music: Music,
  shirt: Shirt,
  scissors: Scissors,
  hammer: Hammer,
  sparkles: Sparkles,
  briefcase: Briefcase,
  "piggy-bank": PiggyBank,
  cake: Cake,
  church: Church,
  bus: Bus,
  fuel: Fuel,
  wifi: Wifi,
  pill: Pill,
  "flower-2": Flower2,
  camera: Camera,
} satisfies Record<string, LucideIcon>

export type NomeIcone = keyof typeof ICONES_DISPONIVEIS

// Chave = 2 primeiros dígitos do pluggy_id (categoria raiz). Filhos herdam o ícone do pai.
// Taxonomia é fixa e read-only (Pluggy retorna 405 p/ criar) → mapa estático basta. Uma categoria
// personalizada tem id "u…" e não cai aqui: o ícone dela é escolha do usuário (coluna `icone`).
const ICONES: Record<string, LucideIcon> = {
  "01": Wallet, //            Renda
  "02": Landmark, //          Empréstimos e financiamento
  "03": TrendingUp, //        Investimentos
  "04": ArrowLeftRight, //    Transferência mesma titularidade
  "05": Send, //              Transferências
  "06": Scale, //             Obrigações legais
  "07": Wrench, //            Serviços
  "08": ShoppingBag, //       Compras
  "09": MonitorSmartphone, // Serviços digitais
  "10": ShoppingCart, //      Supermercado
  "11": UtensilsCrossed, //   Alimentos e bebidas
  "12": Plane, //             Viagens
  "13": HeartHandshake, //    Doações
  "14": Dice5, //             Apostas
  "15": ReceiptText, //       Impostos
  "16": Percent, //           Taxas bancárias
  "17": Home, //              Moradia
  "18": HeartPulse, //        Saúde
  "19": Car, //               Transporte
  "20": ShieldCheck, //       Seguros
  "21": Gamepad2, //          Lazer
  "99": Tag, //               Outros
}

/** Ícone de "sem categoria" — a transação que a resolução devolve como `desconhecida` (§4.5).
 * Distinto do `Tag` genérico de propósito: "não sei o que é isto" e "categoria sem ícone próprio"
 * são estados diferentes, e só o primeiro pede uma ação do usuário. */
export const ICONE_SEM_CATEGORIA = CircleQuestionMark

/** Ícone da categoria por `pluggy_id`. `icone` é a escolha do usuário numa categoria própria e
 * ganha da taxonomia; sem id nenhum, o de "sem categoria". Preferir `useIconeCategoria` quando só
 * se tem o id — ele acha o `icone` sozinho. */
export function iconeCategoria(
  pluggyId: string | null | undefined,
  icone?: string | null
): LucideIcon {
  if (!pluggyId) return ICONE_SEM_CATEGORIA
  if (icone && icone in ICONES_DISPONIVEIS)
    return ICONES_DISPONIVEIS[icone as NomeIcone]
  return ICONES[pluggyId.slice(0, 2)] ?? Tag
}

/** Mesma assinatura de `iconeCategoria`, mas resolvendo o ícone escolhido a partir do id.
 *
 * Existe porque quase toda tela tem só o `categoria_id` em mãos (transação, orçamento,
 * assinatura) — sem isto, uma categoria personalizada apareceria com o ícone genérico em todo
 * lugar menos na tela de configurações, que é justamente o que a coluna `icone` veio resolver.
 */
export function useIconeCategoria(): (
  pluggyId: string | null | undefined
) => LucideIcon {
  const { data } = useCategorias()
  return useMemo(() => {
    const escolhidos = new Map<string, Categoria["icone"]>(
      (data ?? []).filter((c) => c.icone).map((c) => [c.pluggy_id, c.icone])
    )
    return (pluggyId) =>
      iconeCategoria(pluggyId, pluggyId ? escolhidos.get(pluggyId) : null)
  }, [data])
}
