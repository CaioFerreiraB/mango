import {
  Building2,
  ChartCandlestick,
  ChartLine,
  Coins,
  Landmark,
  Layers,
  PiggyBank,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

/** Rótulos pt-BR da taxonomia Pluggy (type/subtype), compartilhados entre Carteira e Visão Geral. */
export const TIPO_LABEL: Record<string, string> = {
  EQUITY: "Renda variável",
  ETF: "ETFs",
  FIXED_INCOME: "Renda fixa",
  MUTUAL_FUND: "Fundos",
  SECURITY: "Previdência",
  COE: "COE",
}

export const SUBTYPE_LABEL: Record<string, string> = {
  REAL_ESTATE_FUND: "FII",
  STOCK: "Ação",
  ETF: "ETF",
  CDB: "CDB",
  INVESTMENT_FUND: "Fundo de investimento",
  FIXED_INCOME: "Renda fixa",
  PGBL: "PGBL",
  VGBL: "VGBL",
  RETIREMENT: "Previdência",
  TREASURY: "Tesouro Direto",
  LCI: "LCI",
  LCA: "LCA",
  CRI: "CRI",
  CRA: "CRA",
  DEBENTURES: "Debênture",
}

export const ICONE_TIPO: Record<string, LucideIcon> = {
  EQUITY: ChartCandlestick,
  ETF: Layers,
  FIXED_INCOME: Landmark,
  MUTUAL_FUND: ChartLine,
  SECURITY: PiggyBank,
  REAL_ESTATE_FUND: Building2,
  STOCK: ChartCandlestick,
  CDB: Landmark,
  TREASURY: Landmark,
  INVESTMENT_FUND: ChartLine,
  PGBL: PiggyBank,
  VGBL: PiggyBank,
  RETIREMENT: PiggyBank,
}

export const rotuloTipo = (t: string) => TIPO_LABEL[t] ?? t
export const rotuloSubtype = (s: string | null | undefined) =>
  s ? (SUBTYPE_LABEL[s] ?? s) : null
export const iconeTipo = (t: string) => ICONE_TIPO[t] ?? Coins

/** Rótulo curto do ativo: subtype quando houver (FII, CDB…), senão o tipo. */
export const rotuloClasse = (type: string, subtype: string | null | undefined) =>
  rotuloSubtype(subtype) ?? rotuloTipo(type)

/** Indexador legível a partir do par (rate_type, rate) do Pluggy — ex.: "IPCA + 6,82% a.a.",
 *  "6,82% a.a." (prefixado), "SELIC + 0,10% a.a.", "110% do CDI". `null` quando não há dado. */
export function rotuloIndexador(
  rateType: string | null | undefined,
  rate: string | number | null | undefined
): string | null {
  const tipo = (rateType ?? "").trim().toUpperCase()
  const num = rate == null || rate === "" ? null : Number(rate)
  const taxa = num != null && Number.isFinite(num) ? `${fmtPct.format(num)}%` : null
  if (tipo === "IPCA" || tipo === "IGPM" || tipo === "IGP-M")
    return taxa ? `${tipo} + ${taxa} a.a.` : tipo
  if (tipo === "SELIC") return taxa ? `SELIC + ${taxa} a.a.` : "SELIC"
  if (tipo === "CDI" || tipo === "DI") return taxa ? `${taxa} do CDI` : "CDI"
  if (tipo === "" || tipo === "PRE" || tipo === "PREFIXADO" || tipo === "FIXED")
    return taxa ? `${taxa} a.a.` : null
  // Indexador desconhecido: mostra o que houver.
  return [tipo || null, taxa ? `+ ${taxa} a.a.` : null].filter(Boolean).join(" ") || null
}

/** Rótulo de uma chave que pode ser subtype OU type (ex.: opção de filtro "Tipo"). */
export const rotuloChave = (s: string) => SUBTYPE_LABEL[s] ?? TIPO_LABEL[s] ?? s

// --- formatação numérica compartilhada (Carteira + drawer) --------------------------------------

export const fmtQtd = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 8 })
export const fmtPct = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 })
/** Percentual com sinal explícito — cor nunca é o único portador de sentido (a11y). */
export const pctTexto = (v: number) => `${v > 0 ? "+" : ""}${fmtPct.format(v)}%`

/** Movimentos do Pluggy (type) → pt-BR. */
export const MOVIMENTO_LABEL: Record<string, string> = {
  BUY: "Aplicação",
  SELL: "Resgate",
  DIVIDEND: "Provento",
  INTEREST: "Rendimento",
  TRANSFER: "Transferência",
  TAX: "Imposto/taxa",
  AMORTIZATION: "Amortização",
}
