import {
  Wallet, Landmark, TrendingUp, ArrowLeftRight, Send, Scale, Wrench,
  ShoppingBag, MonitorSmartphone, ShoppingCart, UtensilsCrossed, Plane,
  HeartHandshake, Dice5, ReceiptText, Percent, Home, HeartPulse, Car,
  ShieldCheck, Gamepad2, Tag,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

// Chave = 2 primeiros dígitos do pluggy_id (categoria raiz). Filhos herdam o ícone do pai.
// Taxonomia é fixa e read-only (Pluggy retorna 405 p/ criar) → mapa estático basta.
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

/** Ícone da categoria por pluggy_id (raiz ou filho). Tag como fallback. */
export function iconeCategoria(pluggyId: string | null | undefined): LucideIcon {
  return ICONES[pluggyId?.slice(0, 2) ?? ""] ?? Tag
}
