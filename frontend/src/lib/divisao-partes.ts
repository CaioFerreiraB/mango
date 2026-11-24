import type { PessoaSelecionada } from "@/components/divisoes/pessoa-multi-picker"
import type { DivisaoDespesa } from "@/lib/api/divisoes"

/** Fatia de cada pessoa por id: centésimos de ponto percentual (porcentagem, 10000 = 100%) ou
 *  centavos (valor). Mesma unidade de `ParteDivisao.valor` no backend. */
export type Partes = Record<number, number>
export type ModoPartes = "porcentagem" | "valor"

export const CEM_POR_CENTO = 10_000

/** O que as fatias têm de somar: 100% ou o valor total. */
export function alvoPartes(modo: ModoPartes, total: number) {
  return modo === "porcentagem" ? CEM_POR_CENTO : total
}

export function somaPartes(pessoas: { id: number }[], partes: Partes) {
  return pessoas.reduce((s, p) => s + (partes[p.id] ?? 0), 0)
}

/** Fatias somam 100% (ou o total) e alguém além de quem pagou tem parte — a mesma regra do backend. */
export function partesValidas(
  modo: ModoPartes,
  total: number,
  pagadorId: number | null,
  pessoas: { id: number }[],
  partes: Partes
) {
  return (
    somaPartes(pessoas, partes) === alvoPartes(modo, total) &&
    pessoas.some((p) => p.id !== pagadorId && (partes[p.id] ?? 0) > 0)
  )
}

/** Payload `partes` da API, só das pessoas na lista (quem saiu da seleção não vai junto). */
export function partesPayload(pessoas: PessoaSelecionada[], partes: Partes) {
  return pessoas.map((p) => ({ usuario_id: p.id, valor: partes[p.id] ?? 0 }))
}

/** Nova fatia de uma pessoa. Com exatamente duas pessoas, a outra vira o complemento (alvo − v,
 *  mínimo 0) — digitar uma já fecha a conta. Com três ou mais, só muda quem foi editado. */
export function comFatia(
  pessoas: { id: number }[],
  partes: Partes,
  id: number,
  v: number,
  alvo: number
): Partes {
  const novas = { ...partes, [id]: v }
  if (pessoas.length === 2) {
    const outra = pessoas.find((p) => p.id !== id)
    if (outra) novas[outra.id] = Math.max(alvo - v, 0)
  }
  return novas
}

/** Mesmo rateio do backend (`_proporcional`): cada um leva o piso da sua fatia e os centavos que
 *  sobram vão para os maiores restos (empate: menor id). Peso zero fica de fora. */
export function proporcional(
  total: number,
  pesos: [number, number][]
): Record<number, number> {
  const ordem = pesos.filter(([, p]) => p > 0).sort((a, b) => a[0] - b[0])
  const soma = ordem.reduce((s, [, p]) => s + p, 0)
  if (soma === 0) return {}
  const fatias = ordem.map(([id, p]) => ({
    id,
    base: Math.floor((total * p) / soma),
    resto: (total * p) % soma,
  }))
  const sobra = total - fatias.reduce((s, f) => s + f.base, 0)
  const extra = new Set(
    [...fatias]
      .sort((a, b) => b.resto - a.resto || a.id - b.id)
      .slice(0, sobra)
      .map((f) => f.id)
  )
  return Object.fromEntries(
    fatias.map((f) => [f.id, f.base + (extra.has(f.id) ? 1 : 0)])
  )
}

/** Reparte `alvo` igualmente; o resto vai para os primeiros. */
export function partesIguais(pessoas: { id: number }[], alvo: number): Partes {
  const base = Math.floor(alvo / pessoas.length)
  const resto = alvo - base * pessoas.length
  return Object.fromEntries(
    pessoas.map((p, i) => [p.id, base + (i < resto ? 1 : 0)])
  )
}

/** Parte de quem não pagou — o que os outros devem; não muda ao vincular sem reajuste. */
export function outrosDaDivisao(d: DivisaoDespesa) {
  return d.participantes
    .filter((p) => p.usuario_id !== d.pago_por_usuario_id)
    .reduce((s, p) => s + p.valor_centavos, 0)
}
