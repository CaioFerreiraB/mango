import type { components } from "./api/schema"

type Posicao = Pick<
  components["schemas"]["CarteiraPosicao"],
  "chave" | "nome" | "code" | "investimento_ids"
>
type Vinculo = Pick<components["schemas"]["InvestimentoRead"], "objetivo_id">

// Mesmo teto do schema InvestimentoPosicaoObjetivo e das consultas de posição.
export const MAX_POSICOES_OBJETIVO = 200

export type PosicaoDisponivel = Posicao & { idsLivres: number[] }

/** Preserva os grupos da carteira, oferecendo apenas seus integrantes livres e conhecidos. */
export function posicoesDisponiveis(
  posicoes: Posicao[],
  investimentos: ReadonlyMap<number, Vinculo>
): PosicaoDisponivel[] {
  return posicoes.flatMap((posicao) => {
    const idsLivres = posicao.investimento_ids.filter((id) => {
      const investimento = investimentos.get(id)
      return investimento != null && investimento.objetivo_id == null
    })
    return idsLivres.length ? [{ ...posicao, idsLivres }] : []
  })
}
