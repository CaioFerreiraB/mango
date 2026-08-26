/**
 * Formatação central de valores e datas.
 *
 * Valores monetários trafegam e são guardados como INTEGER em **centavos** (decisão #2); a UI
 * converte só na exibição. Cortes de período usam o fuso **America/Sao_Paulo** (§4.10).
 */

const fmtMoeda = new Map<string, Intl.NumberFormat>()

/** Centavos (INTEGER) → moeda formatada em pt-BR. Ex.: `formatMoeda(-2167, "USD")` → `-US$ 21,67`. */
export function formatMoeda(centavos: number, moeda: string): string {
  let fmt = fmtMoeda.get(moeda)
  if (!fmt) {
    fmt = new Intl.NumberFormat("pt-BR", { style: "currency", currency: moeda })
    fmtMoeda.set(moeda, fmt)
  }
  return fmt.format(centavos / 100)
}

/** Centavos (INTEGER) → `R$ 1.234,56`. */
export function formatBRL(centavos: number): string {
  return formatMoeda(centavos, "BRL")
}

/**
 * Percentual já em pontos (ex.: `15.42` → `15,42%`). `sinal` força o `+` nos positivos; negativos
 * sempre usam o menos tipográfico `−` (mesmo glifo do `Valor`/`Delta`).
 */
export function formatPct(
  valor: number,
  opts?: { sinal?: boolean; casas?: number }
): string {
  const casas = opts?.casas ?? 2
  const abs = new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(Math.abs(valor))
  const prefixo = valor < 0 ? "−" : opts?.sinal ? "+" : ""
  return `${prefixo}${abs}%`
}

const TZ = "America/Sao_Paulo"
const dateFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ,
  dateStyle: "medium",
})
const dateTimeFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ,
  dateStyle: "medium",
  timeStyle: "short",
})

function toDate(value: string | number | Date): Date {
  return value instanceof Date ? value : new Date(value)
}

/** Data ISO/epoch → `30 de jun. de 2026` (America/Sao_Paulo). */
export function formatDate(value: string | number | Date): string {
  return dateFmt.format(toDate(value))
}

/** Data/hora ISO/epoch → `30 de jun. de 2026, 14:05` (America/Sao_Paulo). */
export function formatDateTime(value: string | number | Date): string {
  return dateTimeFmt.format(toDate(value))
}

// --- Períodos (yyyy-mm-dd, fuso SP) ------------------------------------------------------------
// Datas de período trafegam como `yyyy-mm-dd`. A aritmética trata a string como data civil pura
// (meio-dia UTC evita o dia "virar" por fuso); só `hojeISO` usa o fuso SP para saber o hoje.

const spISO = new Intl.DateTimeFormat("en-CA", { timeZone: TZ }) // en-CA → yyyy-mm-dd

/** Hoje no fuso SP como `yyyy-mm-dd`. */
export function hojeISO(): string {
  return spISO.format(new Date())
}

const mesAnoFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ,
  month: "long",
  year: "numeric",
})

/** Data ISO/epoch → `junho de 2026` (mês por extenso + ano, fuso SP). */
export function formatMesAno(value: string | number | Date): string {
  return mesAnoFmt.format(toDate(value))
}

/** Data ISO/epoch → `yyyy-mm` no fuso SP — chave de agrupamento/filtro por mês. */
export function mesISO(value: string | number | Date): string {
  return spISO.format(toDate(value)).slice(0, 7)
}

function parseISO(iso: string): Date {
  return new Date(`${iso}T12:00:00Z`)
}

export function addDias(iso: string, n: number): string {
  const d = parseISO(iso)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/** Mês corrente até hoje (fuso SP): `[01 do mês, hoje]`. Período fixo dos KPIs do painel. */
export function mesAteHoje(): { inicio: string; fim: string } {
  const fim = hojeISO()
  return { inicio: `${fim.slice(0, 8)}01`, fim }
}

/**
 * Últimos 6 meses **completos** (exclui o mês corrente parcial): `[01 de 6 meses atrás, último dia
 * do mês passado]`. Janela da mini-área de tendência dos cards. Ex.: hoje 2026-07-08 →
 * `[2026-01-01, 2026-06-30]` (jan–jun), 6 buckets mensais.
 */
export function ultimos6MesesCompletos(): { inicio: string; fim: string } {
  const primeiroDoMes = `${hojeISO().slice(0, 8)}01`
  return { inicio: subMeses(primeiroDoMes, 6), fim: addDias(primeiroDoMes, -1) }
}

/**
 * Mesma faixa de dias um mês antes — base do comparativo mês a mês dos KPIs.
 * Ex.: `[2026-07-01, 2026-07-08]` → `[2026-06-01, 2026-06-08]`. O dia é limitado ao último dia do
 * mês de destino quando não existe lá (ex.: 31/07 → 30/06; 31/03 → 28/02).
 */
export function mesmoPeriodoMesAnterior(
  inicio: string,
  fim: string
): { inicio: string; fim: string } {
  return { inicio: mesAntes(inicio), fim: mesAntes(fim) }
}

/** `n` meses antes (civil, fuso-neutro), com o dia limitado ao último dia do mês destino. */
export function subMeses(iso: string, n: number): string {
  const d = parseISO(iso)
  const alvo = new Date(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - n, 1, 12)
  )
  const ultimoDia = new Date(
    Date.UTC(alvo.getUTCFullYear(), alvo.getUTCMonth() + 1, 0, 12)
  ).getUTCDate()
  alvo.setUTCDate(Math.min(d.getUTCDate(), ultimoDia))
  return alvo.toISOString().slice(0, 10)
}

/** Mesma data um mês antes (civil, fuso-neutro), com o dia limitado ao último dia do mês destino. */
function mesAntes(iso: string): string {
  return subMeses(iso, 1)
}

const mesCurto = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ,
  month: "short",
})
const diaFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TZ,
  day: "2-digit",
})

/** Data-only `yyyy-mm-dd` → `5 de ago. de 2026` (sem o off-by-one de fuso do `new Date`). */
export function formatDataISO(iso: string): string {
  return dateFmt.format(parseISO(iso))
}

/** Data-only `yyyy-mm-dd` → badge de evento `{ dia: "05", mes: "AGO" }`. */
export function badgeData(iso: string): { dia: string; mes: string } {
  const d = parseISO(iso)
  return {
    dia: diaFmt.format(d),
    mes: mesCurto.format(d).replace(".", "").toUpperCase(),
  }
}

/** Rótulo curto de um bucket da série para eixo: diária/semanal → `01/06`, mensal → `jun/26`. */
export function formatBucketLabel(
  inicio: string,
  granularidade: "diaria" | "semanal" | "mensal"
): string {
  const [ano, mes, dia] = inicio.split("-")
  if (granularidade === "mensal") {
    const nome = mesCurto.format(parseISO(inicio)).replace(".", "")
    return `${nome}/${ano.slice(2)}`
  }
  return `${dia}/${mes}`
}

/** Iniciais para avatar (fallback sem imagem): até 2 palavras do nome. */
export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  if (partes.length === 0) return "?"
  return partes
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("")
}

/** Número de conta/cartão mascarado — só os últimos 4 dígitos (privacidade). */
export function mascarar(numero: string | null | undefined): string {
  if (!numero) return "—"
  const so = numero.replace(/\s/g, "")
  return so.length <= 4 ? so : `•••• ${so.slice(-4)}`
}

/** Status de fatura pelo vencimento: "Em aberto" enquanto não passou; senão "Fechada". */
export function statusFatura(dueDate: string): {
  rotulo: string
  aberta: boolean
} {
  const aberta = new Date(dueDate).getTime() >= Date.now()
  return { rotulo: aberta ? "Em aberto" : "Fechada", aberta }
}
