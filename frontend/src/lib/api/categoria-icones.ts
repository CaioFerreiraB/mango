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
 * fronteira, esta é a que de fato desenha.
 *
 * O `rotulo` mora aqui junto do componente, e não num segundo mapa, para não existir ícone sem
 * nome legível: a chave é identificador técnico ("utensils-crossed") e o leitor de tela precisa
 * ouvir português. */
export const ICONES_DISPONIVEIS = {
  // Os 22 das raízes do Pluggy, para uma categoria própria conversar com a taxonomia.
  wallet: { icone: Wallet, rotulo: "Carteira" },
  landmark: { icone: Landmark, rotulo: "Banco" },
  "trending-up": { icone: TrendingUp, rotulo: "Investimentos" },
  "arrow-left-right": { icone: ArrowLeftRight, rotulo: "Transferência" },
  send: { icone: Send, rotulo: "Envio" },
  scale: { icone: Scale, rotulo: "Balança" },
  wrench: { icone: Wrench, rotulo: "Ferramenta" },
  "shopping-bag": { icone: ShoppingBag, rotulo: "Sacola" },
  "monitor-smartphone": { icone: MonitorSmartphone, rotulo: "Eletrônicos" },
  "shopping-cart": { icone: ShoppingCart, rotulo: "Carrinho" },
  "utensils-crossed": { icone: UtensilsCrossed, rotulo: "Talheres" },
  plane: { icone: Plane, rotulo: "Avião" },
  "heart-handshake": { icone: HeartHandshake, rotulo: "Doação" },
  "dice-5": { icone: Dice5, rotulo: "Dado" },
  "receipt-text": { icone: ReceiptText, rotulo: "Recibo" },
  percent: { icone: Percent, rotulo: "Porcentagem" },
  home: { icone: Home, rotulo: "Casa" },
  "heart-pulse": { icone: HeartPulse, rotulo: "Saúde" },
  car: { icone: Car, rotulo: "Carro" },
  "shield-check": { icone: ShieldCheck, rotulo: "Escudo" },
  "gamepad-2": { icone: Gamepad2, rotulo: "Videogame" },
  tag: { icone: Tag, rotulo: "Etiqueta" },
  // Os que a taxonomia do banco não cobre — o motivo de existir categoria personalizada.
  "paw-print": { icone: PawPrint, rotulo: "Pata" },
  gift: { icone: Gift, rotulo: "Presente" },
  "graduation-cap": { icone: GraduationCap, rotulo: "Formatura" },
  baby: { icone: Baby, rotulo: "Bebê" },
  dumbbell: { icone: Dumbbell, rotulo: "Halteres" },
  coffee: { icone: Coffee, rotulo: "Café" },
  "book-open": { icone: BookOpen, rotulo: "Livro" },
  music: { icone: Music, rotulo: "Música" },
  shirt: { icone: Shirt, rotulo: "Camiseta" },
  scissors: { icone: Scissors, rotulo: "Tesoura" },
  hammer: { icone: Hammer, rotulo: "Martelo" },
  sparkles: { icone: Sparkles, rotulo: "Brilhos" },
  briefcase: { icone: Briefcase, rotulo: "Maleta" },
  "piggy-bank": { icone: PiggyBank, rotulo: "Cofrinho" },
  cake: { icone: Cake, rotulo: "Bolo" },
  church: { icone: Church, rotulo: "Igreja" },
  bus: { icone: Bus, rotulo: "Ônibus" },
  fuel: { icone: Fuel, rotulo: "Combustível" },
  wifi: { icone: Wifi, rotulo: "Wi-Fi" },
  pill: { icone: Pill, rotulo: "Remédio" },
  "flower-2": { icone: Flower2, rotulo: "Flor" },
  camera: { icone: Camera, rotulo: "Câmera" },
} satisfies Record<
  // Trava de sincronia com o backend, nas DUAS direções: `Record` com união exige todas as chaves
  // (ícone que o backend aceita e falta aqui não compila) e `satisfies` recusa chave excedente
  // (ícone daqui que o backend não aceita também não). Sem `schema.d.ts` isto vira `Record<any,…>`
  // e degrada em silêncio — a trava é para nós, não para o analisador.
  NonNullable<Categoria["icone"]>,
  { icone: LucideIcon; rotulo: string }
>

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
    return ICONES_DISPONIVEIS[icone as NomeIcone].icone
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
