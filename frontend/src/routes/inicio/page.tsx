import {
  ArrowLeftRight,
  ChevronRight,
  CircleCheckBig,
  CreditCard,
  Landmark,
  PiggyBank,
  Target,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"
import { Link } from "react-router"

import { Sparkline } from "@/components/common/graficos-base"
import { BotaoOcultar } from "@/components/common/kpi"
import { EmptyState } from "@/components/common/empty-state"
import { CenaMascote } from "@/components/common/mascote-cena"
import { Selo } from "@/components/common/selo"
import { Valor } from "@/components/common/valor"
import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useMe } from "@/lib/api/auth"
import { useContas, useSaldoContasSerie } from "@/lib/api/contas"
import { useCartoesPainel, useDashboard } from "@/lib/api/dashboard"
import { useResumoDespesasFixas } from "@/lib/api/despesas-fixas"
import { useCarteiraResumo } from "@/lib/api/investimentos"
import { useObjetivos } from "@/lib/api/objetivos"
import { useConsumoOrcamentos } from "@/lib/api/orcamentos"
import { useTransacoes } from "@/lib/api/transacoes"
import {
  formatBRL,
  formatDataCurta,
  formatDate,
  formatPct,
  hojeISO,
  mesAteHoje,
} from "@/lib/format"
import { cn } from "@/lib/utils"

const CHAVE_OCULTO = "mango:dashboard-oculto" // o mesmo modo privacidade do Dashboard

/** Saudação do topo do Início — uma sorteada a cada visita (o jeito descontraído do mango). */
/** `{nome}` vira o primeiro nome do usuário. */
const SAUDACOES = [
  "Olá, {nome}!",
  "Fala, {nome}!",
  "E aí, {nome}!",
  "Opa, {nome}!",
  "Oi, {nome}!",
  "Salve, {nome}!",
  "Bora, {nome}?",
  "Tudo certo, {nome}?",
  "Bom te ver de novo, {nome}!",
  "Que bom te ver, {nome}!",
]
/** Sem nome real (o placeholder "Local" do modo desktop): as mesmas, sem o nome. */
const SAUDACOES_SEM_NOME = [
  "Olá!",
  "Fala aí!",
  "E aí!",
  "Opa!",
  "Oi!",
  "Salve!",
  "Bora?",
  "Tudo certo?",
  "Bom te ver de novo!",
  "Que bom te ver!",
]

/** "Bom dia/Boa tarde/Boa noite" pela hora de Brasília (o fuso de todos os cortes do app). */
function saudacao(): string {
  const h = Number(
    new Intl.DateTimeFormat("pt-BR", {
      hour: "numeric",
      hourCycle: "h23",
      timeZone: "America/Sao_Paulo",
    }).format(new Date())
  )
  return h < 5
    ? "Boa noite"
    : h < 12
      ? "Bom dia"
      : h < 18
        ? "Boa tarde"
        : "Boa noite"
}

/**
 * Início — o hub (usabilidade Nubank, linguagem Wise): saldo com o olho, atalhos redondos para o
 * que se faz todo dia e seções clicáveis, cada uma levando à tela certa. As análises completas
 * moram em /dashboard.
 */
export function InicioPage() {
  const me = useMe()
  const [oculto, setOculto] = useState(() => {
    try {
      return localStorage.getItem(CHAVE_OCULTO) === "1"
    } catch {
      return false
    }
  })
  const alternarOculto = () =>
    setOculto((v) => {
      try {
        localStorage.setItem(CHAVE_OCULTO, v ? "0" : "1")
      } catch {
        // armazenamento bloqueado: vale só nesta visita
      }
      return !v
    })

  const mes = mesAteHoje()
  const dash = useDashboard(mes, "competencia")
  const contas = useContas()
  const serie = useSaldoContasSerie()
  // ponytail: "Local" é o nome-placeholder do modo desktop — sem nome real, saúda sem nome.
  const nome = me.data?.nome?.trim().split(/\s+/)[0]
  // Uma por visita ao Início (não muda a cada re-render nem ao revalidar dados). O relógio basta
  // para variar a frase — não é sorteio que precise de aleatoriedade de verdade.
  const [sorteio] = useState(() => Math.floor(Date.now() / 1000))
  const bancos = contas.data?.filter((c) => c.type === "BANK").length

  // Nenhuma conta conectada: um hub de zeros não diz nada — ensina o próximo passo (como o
  // Dashboard faz).
  if (contas.isSuccess && contas.data.length === 0)
    return (
      <EmptyState
        icon={Landmark}
        cena="money"
        title="Conecte o Open Finance para começar"
        description="Assim que você conectar uma conta pelo Pluggy, o Início mostra seu saldo, o que precisa de atenção e o resumo do mês."
      >
        <Button asChild>
          <Link to="/configuracoes">Conectar conta</Link>
        </Button>
      </EmptyState>
    )

  return (
    <div className="space-y-8">
      <FaixaMarca
        titulo={
          nome && nome !== "Local"
            ? (
                SAUDACOES.at(sorteio % SAUDACOES.length) ?? "Olá, {nome}!"
              ).replace("{nome}", nome)
            : (SAUDACOES_SEM_NOME.at(sorteio % SAUDACOES_SEM_NOME.length) ??
              "Olá!")
        }
        saldo={dash.data?.saldo_total_centavos}
        contas={bancos}
        pontos={serie}
        oculto={oculto}
        onAlternarOculto={alternarOculto}
      />

      <div className="space-y-6">
        <Atalhos pendentes={dash.data?.nao_revisadas ?? 0} />
        <Atencao
          naoRevisadas={dash.data?.nao_revisadas}
          carregando={dash.isLoading}
          erro={dash.isError}
        />
      </div>

      <section aria-labelledby="resumo-titulo" className="space-y-3">
        <h2 id="resumo-titulo" className="text-lg font-bold tracking-tight">
          Seu mês
        </h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[
            SecaoMes,
            SecaoCartao,
            SecaoOrcamento,
            SecaoDespesasFixas,
            SecaoObjetivos,
            SecaoInvestimentos,
          ].map((S, i) => (
            // Onda das seções: 160→240ms, intervalos encolhendo (não uniforme).
            <div
              key={i}
              className="entra"
              style={
                {
                  "--atraso": `${[160, 185, 205, 220, 232, 240][i]}ms`,
                } as React.CSSProperties
              }
            >
              <S oculto={oculto} />
            </div>
          ))}
        </div>
      </section>

      <div
        className="entra"
        style={
          {
            "--atraso": "240ms",
            "--dist": "0px",
            "--dur": "260ms",
          } as React.CSSProperties
        }
      >
        <UltimasTransacoes oculto={oculto} />
      </div>
    </div>
  )
}

// --- faixa de marca -----------------------------------------------------------------------------

/**
 * A identidade do Início (o "roxo do Nubank" do mango): faixa na cor forte do accent, saudação,
 * saldo grande em branco, a curva de 30 dias em sangria e o mascote EM CENA — em pé na borda de
 * baixo da faixa, cortado por ela, ao lado do saldo (nunca por cima dele). Lead da coreografia.
 */
function FaixaMarca({
  titulo,
  saldo,
  contas,
  pontos,
  oculto,
  onAlternarOculto,
}: {
  titulo: string
  saldo?: number
  contas?: number
  pontos: { data: string; saldo_centavos: number }[]
  oculto: boolean
  onAlternarOculto: () => void
}) {
  const dados = useMemo(
    () => pontos.map((p) => ({ rotulo: p.data, valor: p.saldo_centavos })),
    [pontos]
  )
  const variacao =
    dados.length >= 2 ? dados[dados.length - 1].valor - dados[0].valor : null
  return (
    <section
      aria-label="Saldo"
      data-destaque
      className="@container relative isolate entra overflow-hidden rounded-[1.75rem] border border-transparent bg-card shadow-(--shadow-card) dark:border-border/70"
      style={
        {
          "--dist": "12px",
          "--blur": "6px",
          "--dur": "400ms",
        } as React.CSSProperties
      }
    >
      <CenaMascote cena="money" />
      <div className="relative z-10 px-6 pt-6 @md:px-8 @md:pt-8 @4xl:pr-80">
        <p className="text-sm font-semibold text-muted-foreground">
          {saudacao()}
        </p>
        <h1 className="text-[1.75rem] leading-tight font-extrabold tracking-[-0.03em] sm:text-[2rem]">
          {titulo}
        </h1>
        <div className="mt-6 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
          Saldo em contas
          <BotaoOcultar
            oculto={oculto}
            onClick={onAlternarOculto}
            className="size-8 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-ring"
          />
        </div>
        <p className="mt-1 text-[2.5rem] leading-none font-extrabold tracking-[-0.045em] whitespace-nowrap tabular-nums @xl:text-[3.625rem]">
          {saldo != null ? (
            <Valor
              centavos={saldo}
              neutro
              oculto={oculto}
              animado
              className="font-extrabold"
            />
          ) : (
            <span className="text-muted-foreground">R$ ••••</span>
          )}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          {variacao != null && variacao !== 0 ? (
            // Alta realçada no accent; queda em texto neutro (o "−" carrega o sentido, DESIGN.md).
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-3 py-1 font-bold whitespace-nowrap",
                variacao > 0
                  ? "bg-[color-mix(in_oklab,var(--primary)_10%,transparent)] text-accent-ink"
                  : "bg-muted text-foreground"
              )}
            >
              <Valor
                centavos={variacao}
                sinal
                neutro
                oculto={oculto}
                className="font-bold"
              />
              <span className="font-medium text-muted-foreground">
                em 30 dias
              </span>
            </span>
          ) : null}
          {contas === 0 ? (
            // Só cartões conectados: em vez de "0 contas", o caminho para conectar uma.
            <Link
              to="/configuracoes"
              className="inline-flex items-center gap-0.5 rounded-full px-2 py-1 font-bold text-foreground/80 transition-colors hover:bg-muted hover:text-foreground"
            >
              Conectar conta
              <ChevronRight className="size-4" aria-hidden />
            </Link>
          ) : contas != null ? (
            <Link
              to="/contas"
              className="group/contas inline-flex items-center gap-0.5 rounded-full px-2 py-1 font-bold text-foreground/80 transition-colors hover:bg-muted hover:text-foreground"
            >
              {contas === 1 ? "1 conta" : `${contas} contas`}
              <ChevronRight
                className="size-4 transition-transform duration-200 ease-(--ease-out) group-hover/contas:translate-x-0.5"
                aria-hidden
              />
            </Link>
          ) : null}
        </div>
      </div>
      <div className="relative z-[5] mt-3 -mb-px">
        {dados.length >= 2 ? (
          <Sparkline
            dados={dados}
            nome="Saldo"
            altura={96}
            formatarRotulo={formatDate}
            formatarValor={oculto ? () => "R$ ••••" : formatBRL}
            ariaLabel="Saldo somado das contas nos últimos 30 dias"
          />
        ) : (
          <div className="h-8" />
        )}
      </div>
    </section>
  )
}

// --- atalhos -----------------------------------------------------------------------------------

const ATALHOS: { rotulo: string; href: string; icon: LucideIcon }[] = [
  { rotulo: "Transações", href: "/transacoes", icon: ArrowLeftRight },
  { rotulo: "Contas", href: "/contas", icon: Landmark },
  { rotulo: "Faturas", href: "/faturas", icon: CreditCard },
  { rotulo: "Orçamento", href: "/orcamentos", icon: PiggyBank },
  { rotulo: "Objetivos", href: "/objetivos", icon: Target },
  { rotulo: "Investir", href: "/investimentos/visao_geral", icon: TrendingUp },
  { rotulo: "Dividir", href: "/divisoes", icon: Users },
]

/** Atalhos redondos (Nubank): o primeiro — revisar a fila — é a ação do dia, no tom vivo. */
function Atalhos({ pendentes }: { pendentes: number }) {
  return (
    <nav aria-label="Ações rápidas">
      <ul className="grid grid-cols-4 gap-x-2 gap-y-5 sm:flex sm:flex-wrap sm:justify-between sm:gap-x-2">
        <li
          className="entra"
          style={
            {
              "--atraso": "100ms",
              "--dist": "4px",
              "--escala": "0.9",
              "--dur": "300ms",
            } as React.CSSProperties
          }
        >
          <Atalho
            href="/transacoes?pendente=true"
            rotulo="Revisar"
            icon={CircleCheckBig}
            vivo
            contador={pendentes}
          />
        </li>
        {ATALHOS.map((a, i) => (
          // Onda da esquerda p/ direita, intervalos encolhendo: 100→190ms.
          <li
            key={a.href}
            className="entra"
            style={
              {
                "--atraso": `${[130, 152, 168, 178, 184, 188, 190][i]}ms`,
                "--dist": "4px",
                "--escala": "0.9",
                "--dur": "300ms",
              } as React.CSSProperties
            }
          >
            <Atalho href={a.href} rotulo={a.rotulo} icon={a.icon} />
          </li>
        ))}
      </ul>
    </nav>
  )
}

function Atalho({
  href,
  rotulo,
  icon: Icon,
  vivo = false,
  contador = 0,
}: {
  href: string
  rotulo: string
  icon: LucideIcon
  vivo?: boolean
  contador?: number
}) {
  return (
    <Link
      to={href}
      className="group flex w-full flex-col items-center gap-2 rounded-2xl text-center outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:w-[4.75rem]"
    >
      {/* Hover: a cor se enche a partir do centro (::before escalando de 0 a 1) e o ícone fica
          branco e balança uma vez. "Revisar" é amarelo-manga e se enche de tinta escura. */}
      <span
        className={cn(
          "relative isolate grid size-14 place-items-center rounded-full border transition-transform duration-150 ease-out group-active:scale-93 motion-reduce:group-active:scale-100",
          "before:absolute before:inset-0 before:-z-10 before:scale-0 before:rounded-full before:transition-transform before:duration-300 before:ease-(--ease-out) group-hover:before:scale-100 group-focus-visible:before:scale-100 motion-reduce:before:transition-none",
          vivo
            ? "border-transparent bg-manga text-manga-tinta group-hover:text-background before:bg-foreground"
            : "border-transparent bg-[color-mix(in_oklab,var(--primary)_13%,var(--background))] text-accent-icone group-hover:text-primary-foreground before:bg-marca-forte"
        )}
      >
        <Icon
          className="size-6 transition-colors duration-200 group-hover:animate-[balanca_480ms_var(--ease-out)] motion-reduce:group-hover:animate-none"
          aria-hidden
        />
        {contador > 0 ? (
          <span className="absolute -top-1.5 -right-2 z-10 min-w-5 rounded-full bg-foreground px-1.5 py-0.5 text-[0.6875rem] leading-none font-extrabold text-background tabular-nums ring-2 ring-background">
            {contador > 99 ? "99+" : contador}
            <span className="sr-only"> pendentes</span>
          </span>
        ) : null}
      </span>
      <span className="text-[0.8125rem] leading-tight font-semibold transition-colors duration-200 group-hover:text-accent-ink">
        {rotulo}
      </span>
    </Link>
  )
}

// --- "precisa da sua atenção" -----------------------------------------------------------------

/** O que pede ação agora, em linguagem direta: fila de revisão, contas atrasadas, categorias
 *  estouradas. Sem nada pendente, o mascote comemora. */
function Atencao({
  naoRevisadas,
  carregando,
  erro,
}: {
  naoRevisadas?: number
  /** Estado da consulta do dashboard (de onde vem `naoRevisadas`). */
  carregando: boolean
  erro: boolean
}) {
  const df = useResumoDespesasFixas()
  const [ano, mes] = hojeISO().split("-").map(Number)
  const consumo = useConsumoOrcamentos(ano, mes)
  const estouradas = (consumo.data?.itens ?? []).filter(
    (i) => i.tipo === "despesa" && !i.suprimido && i.percentual >= 100
  ).length
  const atrasadas = df.data?.atrasadas.qtd ?? 0
  const itens: { texto: string; href: string; tom: "aviso" | "perigo" }[] = []
  if (naoRevisadas)
    itens.push({
      texto: `${naoRevisadas} ${naoRevisadas === 1 ? "transação para revisar" : "transações para revisar"}`,
      href: "/transacoes?pendente=true",
      tom: "aviso",
    })
  if (atrasadas)
    itens.push({
      texto: `${atrasadas} ${atrasadas === 1 ? "despesa fixa atrasada" : "despesas fixas atrasadas"}`,
      href: "/despesas-fixas",
      tom: "perigo",
    })
  if (estouradas)
    itens.push({
      texto: `${estouradas} ${estouradas === 1 ? "categoria acima do orçamento" : "categorias acima do orçamento"}`,
      href: "/orcamentos",
      tom: "perigo",
    })

  return (
    <section
      aria-labelledby="atencao-titulo"
      className="flex entra flex-col rounded-2xl border border-transparent bg-card p-5 shadow-(--shadow-card) md:p-6 dark:border-border/70"
      style={{ "--atraso": "60ms" } as React.CSSProperties}
    >
      <h2 id="atencao-titulo" className="text-base font-extrabold">
        Precisa da sua atenção
      </h2>
      {/* "Tudo em dia" só com as três fontes respondidas: carregando ou com falha, não dá para
          afirmar que não há nada pendente. */}
      {itens.length === 0 &&
      (carregando || df.isLoading || consumo.isLoading) ? (
        <div className="mt-3 space-y-2" aria-hidden>
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : itens.length === 0 && (erro || df.isError || consumo.isError) ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Não foi possível conferir as pendências agora.
        </p>
      ) : itens.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Tudo em dia por aqui. Nada atrasado, nada para revisar.
        </p>
      ) : (
        <ul className="-mx-2 mt-3 space-y-1 lg:grid lg:grid-cols-3 lg:gap-2 lg:space-y-0">
          {itens.map((i) => (
            <li key={i.href}>
              <Link
                to={i.href}
                className="group flex items-center gap-3 rounded-xl px-2 py-2.5 text-sm font-semibold transition-colors hover:bg-muted"
              >
                <span
                  className={cn(
                    "size-2.5 shrink-0 rounded-full",
                    i.tom === "perigo" ? "bg-negative" : "bg-warning"
                  )}
                  aria-hidden
                />
                <span className="flex-1">{i.texto}</span>
                <ChevronRight
                  className="size-4 text-muted-foreground transition-transform duration-200 ease-(--ease-out) group-hover:translate-x-0.5 group-hover:text-accent-icone motion-reduce:transition-none"
                  aria-hidden
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// --- seções clicáveis (Nubank) -----------------------------------------------------------------

/** Seção do Início: o card inteiro é o link (título + chevron no topo, dado embaixo). */
function Secao({
  titulo,
  href,
  icon: Icon,
  carregando,
  children,
}: {
  titulo: string
  href: string
  icon: LucideIcon
  carregando?: boolean
  children: ReactNode
}) {
  return (
    <Link
      to={href}
      className="group flex h-full min-h-40 superficie-interativa flex-col rounded-2xl border border-transparent bg-card p-5 shadow-(--shadow-card) outline-none focus-visible:ring-3 focus-visible:ring-ring/50 md:p-6 dark:border-border/70"
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="grid size-10 place-items-center rounded-full bg-muted text-accent-icone transition-transform duration-300 ease-(--ease-out) group-hover:scale-108 group-hover:-rotate-6 motion-reduce:transition-none"
        >
          <Icon className="size-[1.125rem]" />
        </span>
        <h3 className="flex-1 font-extrabold">{titulo}</h3>
        <ChevronRight
          className="size-5 text-muted-foreground transition-transform duration-200 ease-(--ease-out) group-hover:translate-x-0.5 group-hover:text-accent-icone motion-reduce:transition-none"
          aria-hidden
        />
      </div>
      <div className="mt-5 flex flex-1 flex-col justify-end">
        {carregando ? (
          <Skeleton className="h-14 w-full rounded-xl" />
        ) : (
          // Dado que chega depois do skeleton entra com fade (sem "pulo").
          <div className="animate-[entrada-fade_240ms_ease-out] motion-reduce:animate-none">
            {children}
          </div>
        )}
      </div>
    </Link>
  )
}

function Numero({ children }: { children: ReactNode }) {
  return (
    <p className="text-[1.625rem] leading-none font-extrabold tracking-[-0.03em] tabular-nums">
      {children}
    </p>
  )
}

function Linha({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-sm text-muted-foreground">{children}</p>
}

function Barra({ pct, tom }: { pct: number; tom: string }) {
  return (
    <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
      <div
        className={cn(
          "h-full origin-left animate-[barra-cresce_700ms_var(--ease-out)_both] rounded-full motion-reduce:animate-none",
          tom
        )}
        style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}
      />
    </div>
  )
}

function SecaoMes({ oculto }: { oculto: boolean }) {
  const { data, isLoading } = useDashboard(mesAteHoje(), "competencia")
  return (
    <Secao
      titulo="Este mês"
      href="/dashboard"
      icon={ArrowLeftRight}
      carregando={isLoading}
    >
      {data ? (
        <>
          <Numero>
            <Valor
              centavos={data.resultado_centavos}
              sinal
              oculto={oculto}
              className="font-extrabold"
            />
          </Numero>
          <Linha>
            Entrou{" "}
            <Valor centavos={data.entradas_centavos} neutro oculto={oculto} /> ·
            saiu{" "}
            <Valor centavos={data.saidas_centavos} neutro oculto={oculto} />
          </Linha>
        </>
      ) : null}
    </Secao>
  )
}

function SecaoCartao({ oculto }: { oculto: boolean }) {
  const { data, isLoading } = useCartoesPainel()
  const vence = data?.cartoes
    .map((c) => c.vence)
    .filter((v): v is string => !!v)
    .sort()[0]
  const disponivel = data?.cartoes.reduce(
    (s, c) => s + (c.disponivel_centavos ?? 0),
    0
  )
  return (
    <Secao
      titulo="Cartão de crédito"
      href="/faturas"
      icon={CreditCard}
      carregando={isLoading}
    >
      {data ? (
        <>
          <p className="text-xs font-medium text-muted-foreground">
            Fatura atual
          </p>
          <Numero>
            <Valor
              centavos={data.fatura_atual_centavos}
              neutro
              oculto={oculto}
              className="font-extrabold"
            />
          </Numero>
          <Linha>
            {vence
              ? `Vence ${formatDataCurta(vence)}`
              : "Sem vencimento próximo"}
            {disponivel ? (
              <>
                {" · "}limite livre{" "}
                <Valor centavos={disponivel} neutro oculto={oculto} />
              </>
            ) : null}
          </Linha>
        </>
      ) : null}
    </Secao>
  )
}

function SecaoOrcamento({ oculto }: { oculto: boolean }) {
  const [ano, mes] = hojeISO().split("-").map(Number)
  const { data, isLoading } = useConsumoOrcamentos(ano, mes)
  const itens = (data?.itens ?? []).filter(
    (i) => i.tipo === "despesa" && !i.suprimido
  )
  const limite = itens.reduce((s, i) => s + i.limite_centavos, 0)
  const gasto =
    itens.reduce((s, i) => s + i.realizado_centavos, 0) +
    (data?.nao_planejado_despesa_centavos ?? 0)
  // Estado pela razão exata; o arredondamento é só do texto (99,6% não pode virar "estourado").
  const razao = limite ? gasto / limite : 0
  const pct = Math.round(razao * 100)
  const restante = limite - gasto
  return (
    <Secao
      titulo="Orçamento"
      href="/orcamentos"
      icon={PiggyBank}
      carregando={isLoading}
    >
      {limite ? (
        <>
          <p className="text-xs font-medium text-muted-foreground">
            {restante >= 0 ? "Ainda pode gastar" : "Passou do orçamento em"}
          </p>
          <Numero>
            <Valor
              centavos={Math.abs(restante)}
              neutro
              oculto={oculto}
              className="font-extrabold"
            />
          </Numero>
          <Barra
            pct={razao * 100}
            tom={
              razao >= 1
                ? "bg-negative"
                : razao >= 0.75
                  ? "bg-warning"
                  : "bg-success"
            }
          />
          <Linha>{pct}% do limite do mês usado</Linha>
        </>
      ) : (
        <Linha>Defina limites por categoria para acompanhar o mês.</Linha>
      )}
    </Secao>
  )
}

function SecaoDespesasFixas({ oculto }: { oculto: boolean }) {
  const { data, isLoading } = useResumoDespesasFixas()
  const proxima = data?.proximos.find((p) => p.situacao !== "paga")
  const total = data
    ? data.pagas.qtd + data.abertas.qtd + data.atrasadas.qtd
    : 0
  return (
    <Secao
      titulo="Despesas fixas"
      href="/despesas-fixas"
      icon={CircleCheckBig}
      carregando={isLoading}
    >
      {data?.tem_despesas ? (
        <>
          <Numero>
            {data.pagas.qtd}
            <span className="text-base font-semibold text-muted-foreground">
              {" "}
              de {total} pagas
            </span>
          </Numero>
          <Barra
            pct={total ? (data.pagas.qtd / total) * 100 : 0}
            tom="bg-success"
          />
          <div className="mt-2 flex min-w-0 flex-col items-start gap-1.5 text-sm text-muted-foreground">
            {data.atrasadas.qtd ? (
              <Selo tom="perigo">
                {data.atrasadas.qtd}{" "}
                {data.atrasadas.qtd === 1 ? "atrasada" : "atrasadas"}
              </Selo>
            ) : null}
            {proxima ? (
              <span className="max-w-full min-w-0 truncate">
                Próxima: {proxima.descricao},{" "}
                <Valor
                  centavos={proxima.valor_centavos}
                  neutro
                  oculto={oculto}
                />
              </span>
            ) : null}
          </div>
        </>
      ) : (
        <Linha>
          Cadastre aluguel, luz e parcelas para não perder vencimentos.
        </Linha>
      )}
    </Secao>
  )
}

function SecaoObjetivos({ oculto }: { oculto: boolean }) {
  const { data, isLoading } = useObjetivos()
  const objetivos = data ?? []
  const alocado = objetivos.reduce((s, o) => s + o.valor_guardado_centavos, 0)
  const alvo = objetivos.reduce((s, o) => s + o.valor_alvo_centavos, 0)
  const atingido = objetivos.reduce(
    (s, o) => s + Math.min(o.valor_guardado_centavos, o.valor_alvo_centavos),
    0
  )
  const pct = alvo ? Math.floor((atingido / alvo) * 100) : 0
  return (
    <Secao
      titulo="Objetivos"
      href="/objetivos"
      icon={Target}
      carregando={isLoading}
    >
      {objetivos.length ? (
        <>
          <p className="text-xs font-medium text-muted-foreground">Guardado</p>
          <Numero>
            <Valor
              centavos={alocado}
              neutro
              oculto={oculto}
              className="font-extrabold"
            />
          </Numero>
          <Barra pct={pct} tom="bg-primary" />
          <Linha>
            {pct}% das metas · {objetivos.length}{" "}
            {objetivos.length === 1 ? "objetivo" : "objetivos"}
          </Linha>
        </>
      ) : (
        <Linha>Crie uma meta e vincule contas ou investimentos a ela.</Linha>
      )}
    </Secao>
  )
}

function SecaoInvestimentos({ oculto }: { oculto: boolean }) {
  const { data, isLoading } = useCarteiraResumo()
  const t = data?.totais
  return (
    <Secao
      titulo="Investimentos"
      href="/investimentos/visao_geral"
      icon={TrendingUp}
      carregando={isLoading}
    >
      {t && t.quantidade_ativos > 0 ? (
        <>
          <p className="text-xs font-medium text-muted-foreground">
            Patrimônio
          </p>
          <Numero>
            <Valor
              centavos={t.valor_centavos}
              neutro
              oculto={oculto}
              className="font-extrabold"
            />
          </Numero>
          <Linha>
            {t.resultado_centavos != null ? (
              <>
                <Valor centavos={t.resultado_centavos} sinal oculto={oculto} />
                {t.resultado_pct != null
                  ? ` (${formatPct(t.resultado_pct)})`
                  : ""}{" "}
                de resultado
              </>
            ) : (
              `${t.quantidade_ativos} ativos`
            )}
          </Linha>
        </>
      ) : (
        <Linha>
          Seus investimentos aparecem aqui quando a corretora sincronizar.
        </Linha>
      )}
    </Secao>
  )
}

// --- últimas transações ------------------------------------------------------------------------

function UltimasTransacoes({ oculto }: { oculto: boolean }) {
  const ultimas = useTransacoes({
    ocultar_pagamento_fatura: true,
    ocultar_futuras: true,
    limit: 6,
  })
  return (
    <section aria-labelledby="ultimas-titulo" className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 id="ultimas-titulo" className="text-lg font-bold tracking-tight">
          Últimas transações
        </h2>
        <Link
          to="/transacoes"
          className="text-sm font-semibold text-accent-ink hover:underline"
        >
          Ver todas
        </Link>
      </div>
      <div className="rounded-2xl border border-transparent bg-card p-2 shadow-(--shadow-card) md:p-3 dark:border-border/70">
        {ultimas.isLoading ? (
          <Skeleton className="my-2 h-64 w-full rounded-xl" />
        ) : ultimas.isError ? (
          // Falha não é "nenhuma transação": diz o que houve e deixa tentar de novo.
          <div className="flex flex-col items-center gap-3 py-8 text-center text-sm text-muted-foreground">
            Não foi possível carregar as transações.
            <Button
              variant="outline"
              size="sm"
              onClick={() => ultimas.refetch()}
            >
              Tentar de novo
            </Button>
          </div>
        ) : ultimas.data?.items.length ? (
          <TransacoesTabela
            items={ultimas.data.items}
            semMoldura
            compacta
            oculto={oculto}
          />
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Nenhuma transação ainda. Elas chegam no próximo sync.
          </p>
        )}
      </div>
    </section>
  )
}
