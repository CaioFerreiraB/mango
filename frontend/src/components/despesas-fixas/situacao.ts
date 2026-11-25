import { TONS_SELO, type TomSelo } from "@/components/common/selo-tons"
import type {
  SituacaoDespesa,
  SituacaoOcorrencia,
} from "@/lib/api/despesas-fixas"

export type Situacao = SituacaoDespesa | SituacaoOcorrencia

/** Texto e tom por situação (tons compartilhados do `Selo`). Em aberto (ainda no prazo) é neutro
 *  de propósito: a única cor quente é a de atraso, e "vence hoje" fica no aviso — senão laranja e
 *  coral se confundem na barra e nos selos. `switch` exaustivo: nenhuma situação fica de fora. */
export function estiloSituacao(s: Situacao): {
  texto: string
  tom: TomSelo
  ponto: string
} {
  const com = (texto: string, tom: TomSelo) => ({
    texto,
    tom,
    ponto: TONS_SELO[tom].ponto,
  })
  switch (s) {
    case "atrasada":
      return com("Atrasada", "perigo")
    case "vence_hoje":
      return com("Vence hoje", "aviso")
    case "em_aberto":
    case "aberta":
      return com("Em aberto", "neutro")
    case "paga":
      return com("Paga", "sucesso")
    case "pulada":
      return com("Pulada", "apagado")
    case "em_dia":
      return com("Sem vencimento no mês", "apagado")
    case "inativa":
      return com("Inativa", "apagado")
  }
}
