import { useLayoutEffect, useRef } from "react"

import { formatBRL } from "@/lib/format"
import { cn } from "@/lib/utils"

/** Escrita direta no nó de texto que o React criou (o React mantém a mesma referência). */
function escrever(no: ChildNode, texto: string) {
  no.nodeValue = texto
}

/**
 * Tween do número quando o valor MUDA (troca de período/visão) — nunca na montagem. Escreve direto
 * no nó de texto que o React já criou (`nodeValue`), sem re-render por frame; ao fim o texto é
 * idêntico ao que o React renderizou. Reduced motion: troca seca.
 */
function useTween(
  ref: React.RefObject<HTMLSpanElement | null>,
  centavos: number,
  formatar: (c: number) => string,
  ativo: boolean
) {
  const anterior = useRef(centavos)
  const fmt = useRef(formatar)
  useLayoutEffect(() => {
    fmt.current = formatar
  })
  // Layout effect: volta o texto ao valor anterior ANTES do paint — sem 1 frame do valor final.
  useLayoutEffect(() => {
    const de = anterior.current
    anterior.current = centavos
    const no = ref.current?.firstChild
    if (!ativo || de === centavos || !no || no.nodeType !== Node.TEXT_NODE)
      return
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    const formatar = fmt.current
    let escrito = formatar(de)
    escrever(no, escrito)
    const t0 = performance.now()
    const duracao = 480
    let raf = 0
    const passo = (t: number) => {
      const p = Math.min((t - t0) / duracao, 1)
      const e = 1 - (1 - p) ** 4 // ease-out quart
      escrito = formatar(Math.round(de + (centavos - de) * e))
      escrever(no, escrito)
      if (p < 1) raf = requestAnimationFrame(passo)
    }
    raf = requestAnimationFrame(passo)
    return () => {
      cancelAnimationFrame(raf)
      // Só devolve o valor final se o texto ainda é o que a animação escreveu: se o React já o
      // trocou (ex.: "R$ ••••" ao ocultar), reescrever aqui vazaria o número escondido.
      if (no.textContent === escrito) escrever(no, formatar(centavos))
    }
  }, [centavos, ativo, ref])
}

/**
 * Valor monetário (centavos → BRL). Cor por sinal, **sempre** com o sinal visível — cor nunca é o
 * único portador de sentido (acessibilidade, DESIGN.md). `sinal` prefixa `+` em créditos.
 *
 * Azul (positivo) só aparece junto do `+`: saldo, limite, orçado e meta são grandezas, não fluxos,
 * e ficam na cor do texto. Negativo também fica na cor do texto (`--negative-ink` é neutro): o "-"
 * carrega o sentido; a framboesa da saída só aparece em preenchimento (barras, pontos, gráficos).
 */
export function Valor({
  centavos,
  sinal = false,
  neutro = false,
  oculto = false,
  absoluto = false,
  quebraMoeda = false,
  animado = false,
  className,
}: {
  centavos: number
  sinal?: boolean
  /** Sem cor por sinal — usa a cor de texto padrão (o `sinal` já carrega o sentido). */
  neutro?: boolean
  /** Modo privacidade: mascara o número (mantém o layout), sem cor por sinal. */
  oculto?: boolean
  /** Mostra `Math.abs(centavos)` (sem "-") — a cor continua vindo do sinal real, então um
   *  valor negativo ainda pode aparecer em vermelho, só sem o sinal de menos no texto. */
  absoluto?: boolean
  /** Card estreito: permite quebrar linha só entre "R$" e o número (Intl usa NBSP ali), nunca
   *  dentro do número nem depois do "-" — número partido é número ambíguo. */
  quebraMoeda?: boolean
  /** Tween quando o valor muda (herói e KPIs). Ignorado com `quebraMoeda`/`oculto`. */
  animado?: boolean
  className?: string
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const cor =
    oculto || neutro
      ? undefined
      : centavos < 0
        ? "text-negative-ink"
        : centavos > 0
          ? sinal
            ? "text-positive-ink"
            : undefined
          : "text-muted-foreground"
  const exibido = absoluto ? Math.abs(centavos) : centavos
  const formatar = (c: number) =>
    sinal && c > 0 ? `+${formatBRL(c)}` : formatBRL(c)
  const texto = oculto ? "R$ ••••" : formatar(exibido)
  useTween(ref, exibido, formatar, animado && !quebraMoeda && !oculto)
  const [moeda, numero] = texto.split("\u00a0")
  return (
    // Sem `quebraMoeda` o valor é indivisível: o "-" do negativo é ponto de quebra para o browser.
    <span
      ref={ref}
      className={cn(
        "font-medium tabular-nums",
        !quebraMoeda && "whitespace-nowrap",
        cor,
        className
      )}
    >
      {quebraMoeda && numero ? (
        <>
          <span className="whitespace-nowrap">{moeda}</span>{" "}
          <span className="whitespace-nowrap">{numero}</span>
        </>
      ) : (
        texto
      )}
    </span>
  )
}
