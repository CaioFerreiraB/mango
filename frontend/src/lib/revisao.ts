/**
 * Estado de revisão de uma transação (§4.3) — espelho no cliente da regra do backend
 * (`app/services/revisao.py`).
 *
 * O usuário escolhe em Configurações → Preferências a data a partir da qual quer revisar. O que
 * veio antes tem a revisão *ignorada*: não é marcado como revisado, só sai da fila. O corte é
 * inclusivo (o próprio dia escolhido já pede revisão) e a comparação é no dia civil de São Paulo —
 * `transacao.date` chega em UTC, e uma compra de madrugada pertence ao dia anterior por aqui.
 */
import { diaCivilSP } from "@/lib/format"

export type EstadoRevisao = "revisado" | "pendente" | "ignorado"

export function estadoRevisao(
  revisada: boolean,
  data: string,
  revisaoDesde: string | null | undefined
): EstadoRevisao {
  if (revisada) return "revisado"
  if (revisaoDesde && diaCivilSP(data) < revisaoDesde) return "ignorado"
  return "pendente"
}

/**
 * O blur do campo de corte deve gravar?
 *
 * Não grava só quando o foco está indo para o próprio botão "Limpar" — senão a data editada sairia
 * em paralelo com o `null` e, chegando depois, ressuscitaria o corte.
 *
 * O `refLimpar &&` NÃO é redundante: sem data salva o botão não é renderizado (ref nula) e clicar
 * em área não-focável dá `relatedTarget` nulo. Sem essa checagem, `null === null` engoliria a
 * PRIMEIRA gravação — justamente a que importa.
 */
export function deveGravarNoBlur(
  relatedTarget: EventTarget | null,
  refLimpar: EventTarget | null
): boolean {
  return !(refLimpar && relatedTarget === refLimpar)
}
