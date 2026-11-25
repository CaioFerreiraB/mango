import type {
  SituacaoDespesa,
  SituacaoOcorrencia,
} from "@/lib/api/despesas-fixas"

export type Situacao = SituacaoDespesa | SituacaoOcorrencia

const PAGA = {
  badge:
    "bg-[#e7f7ef] text-[#0ca678] dark:bg-emerald-500/15 dark:text-emerald-400",
  ponto: "bg-[#0ca678]",
}
// Em aberto (ainda no prazo) é neutro de propósito: a única cor quente é a de atraso, e "vence
// hoje" fica no âmbar — senão laranja e coral se confundem na barra e nos badges.
const ABERTA = {
  badge: "bg-muted text-foreground",
  ponto: "bg-muted-foreground",
}
const HOJE = {
  badge: "bg-[#fef3c7] text-[#92400e] dark:bg-amber-500/15 dark:text-amber-300",
  ponto: "bg-[#f59e0b]",
}
const NEUTRA = {
  badge: "bg-muted text-muted-foreground",
  ponto: "bg-muted-foreground",
}

/** Texto e cores por situação. `switch` exaustivo: o TS garante que nenhuma fica de fora. */
export function estiloSituacao(s: Situacao) {
  switch (s) {
    case "atrasada":
      return {
        texto: "Atrasada",
        badge: "bg-negative/10 text-negative-ink",
        ponto: "bg-negative",
      }
    case "vence_hoje":
      return { texto: "Vence hoje", ...HOJE }
    case "em_aberto":
    case "aberta":
      return { texto: "Em aberto", ...ABERTA }
    case "paga":
      return { texto: "Paga", ...PAGA }
    case "pulada":
      return { texto: "Pulada", ...NEUTRA }
    case "em_dia":
      return { texto: "Sem vencimento no mês", ...NEUTRA }
    case "inativa":
      return { texto: "Inativa", ...NEUTRA }
  }
}
