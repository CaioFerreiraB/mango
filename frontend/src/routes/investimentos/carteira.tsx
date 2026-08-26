import {
  AlertTriangle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Coins,
  Search,
  SlidersHorizontal,
  TrendingUp,
} from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router"

import { AvatarBanco } from "@/components/contas/avatar-banco"
import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { AtivoDrawer } from "@/components/investimentos/ativo-drawer"
import { SyncButton } from "@/components/sync-button"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  useCarteiraResumo,
  useVisaoGeral,
  type CarteiraPosicao,
} from "@/lib/api/investimentos"
import { formatBRL } from "@/lib/format"
import {
  fmtPct,
  fmtQtd,
  ICONE_TIPO,
  pctTexto,
  rotuloChave,
  rotuloClasse,
} from "@/lib/investimento-taxonomia"

// --- classes (abas de topo, derivadas de type/subtype) ------------------------------------------
// "Exterior" (país) e agrupar por Setor/Moeda ficam de fora: o Pluggy não sincroniza esses campos.

type Classe = {
  id: string
  label: string
  match: (p: CarteiraPosicao) => boolean
}

const CLASSES: Classe[] = [
  { id: "todos", label: "Todos os ativos", match: () => true },
  {
    id: "renda_fixa",
    label: "Renda fixa",
    match: (p) => p.type === "FIXED_INCOME",
  },
  {
    id: "acoes",
    label: "Ações",
    match: (p) => p.type === "EQUITY" && p.subtype !== "REAL_ESTATE_FUND",
  },
  { id: "fiis", label: "FIIs", match: (p) => p.subtype === "REAL_ESTATE_FUND" },
  { id: "etfs", label: "ETFs", match: (p) => p.type === "ETF" },
  {
    id: "outros",
    label: "Outros",
    match: (p) => !["FIXED_INCOME", "EQUITY", "ETF"].includes(p.type),
  },
]

type SortCol =
  | "ativo"
  | "tipo"
  | "instituicao"
  | "quantidade"
  | "preco"
  | "cotacao"
  | "investido"
  | "valor"
  | "resultado"
  | "participacao"

const num = (v: number | null | undefined) => v ?? Number.NEGATIVE_INFINITY

function comparar(
  a: CarteiraPosicao,
  b: CarteiraPosicao,
  col: SortCol
): number {
  switch (col) {
    case "ativo":
      return (a.code ?? a.nome ?? "").localeCompare(b.code ?? b.nome ?? "")
    case "tipo":
      return rotuloClasse(a.type, a.subtype).localeCompare(
        rotuloClasse(b.type, b.subtype)
      )
    case "instituicao":
      return (a.instituicao ?? "").localeCompare(b.instituicao ?? "")
    case "quantidade":
      return num(a.quantidade) - num(b.quantidade)
    case "preco":
      return num(a.preco_medio_centavos) - num(b.preco_medio_centavos)
    case "cotacao":
      return num(a.cotacao_centavos) - num(b.cotacao_centavos)
    case "investido":
      return num(a.investido_centavos) - num(b.investido_centavos)
    case "valor":
      return a.valor_centavos - b.valor_centavos
    case "resultado":
      return num(a.resultado_pct) - num(b.resultado_pct)
    case "participacao":
      return num(a.participacao_pct) - num(b.participacao_pct)
  }
}

export function CarteiraPage() {
  const resumo = useCarteiraResumo()
  const visao = useVisaoGeral()

  const [busca, setBusca] = useState("")
  const [classe, setClasse] = useState("todos")
  const [filtroInstituicao, setFiltroInstituicao] = useState<string | null>(
    null
  )
  const [filtroSubtype, setFiltroSubtype] = useState<string | null>(null)
  const [ordenacao, setOrdenacao] = useState<{
    col: SortCol
    dir: "asc" | "desc"
  }>({
    col: "valor",
    dir: "desc",
  })
  const [pagina, setPagina] = useState(1)
  const [porPagina, setPorPagina] = useState(10)
  const [selecionada, setSelecionada] = useState<CarteiraPosicao | null>(null)

  const posicoes = useMemo(() => resumo.data?.posicoes ?? [], [resumo.data])

  // Instituições/subtypes presentes → opções do "Mais filtros".
  const instituicoes = useMemo(
    () =>
      [
        ...new Set(
          posicoes.map((p) => p.instituicao).filter((x): x is string => !!x)
        ),
      ].sort(),
    [posicoes]
  )
  const subtypes = useMemo(
    () => [...new Set(posicoes.map((p) => p.subtype ?? p.type))].sort(),
    [posicoes]
  )

  const classeAtiva = CLASSES.find((c) => c.id === classe) ?? CLASSES[0]
  const filtradas = useMemo(() => {
    const q = busca.trim().toLowerCase()
    const lista = posicoes.filter(
      (p) =>
        classeAtiva.match(p) &&
        (!q ||
          (p.code ?? "").toLowerCase().includes(q) ||
          (p.nome ?? "").toLowerCase().includes(q) ||
          (p.instituicao ?? "").toLowerCase().includes(q)) &&
        (!filtroInstituicao || p.instituicao === filtroInstituicao) &&
        (!filtroSubtype || (p.subtype ?? p.type) === filtroSubtype)
    )
    const sinal = ordenacao.dir === "asc" ? 1 : -1
    return [...lista].sort((a, b) => sinal * comparar(a, b, ordenacao.col))
  }, [
    posicoes,
    classeAtiva,
    busca,
    filtroInstituicao,
    filtroSubtype,
    ordenacao,
  ])

  const totalPaginas = Math.max(1, Math.ceil(filtradas.length / porPagina))
  const paginaSegura = Math.min(pagina, totalPaginas)
  const visiveis = filtradas.slice(
    (paginaSegura - 1) * porPagina,
    paginaSegura * porPagina
  )

  function reiniciar<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v)
      setPagina(1)
    }
  }
  function ordenarPor(col: SortCol) {
    setOrdenacao((o) =>
      o.col === col
        ? { col, dir: o.dir === "asc" ? "desc" : "asc" }
        : { col, dir: "desc" }
    )
  }
  const filtrosAtivos = (filtroInstituicao ? 1 : 0) + (filtroSubtype ? 1 : 0)

  if (resumo.isError) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Não foi possível carregar a carteira"
        description="Tente novamente em instantes."
      />
    )
  }
  if (resumo.isLoading || !resumo.data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  const totais = resumo.data.totais
  if (totais.quantidade_ativos === 0) {
    return (
      <div className="space-y-6">
        <Cabecalho />
        <EmptyState
          icon={TrendingUp}
          title="Nenhum investimento importado"
          description="Conecte uma conta com investimentos pelo Pluggy e sincronize — a carteira chega pronta, com valores e impostos já calculados."
        >
          <Button asChild>
            <Link to="/configuracoes">Conectar conta</Link>
          </Button>
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Cabecalho />

      {/* Resumo (KPIs) — sem "valor disponível para investir" (não existe no modelo). */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Kpi
          label="Valor da carteira"
          hint={`Líquido ${formatBRL(totais.liquido_centavos)}`}
        >
          <Valor
            centavos={totais.valor_centavos}
            neutro
            className="text-2xl font-bold"
          />
        </Kpi>
        <Kpi label="Valor investido">
          <Valor
            centavos={totais.investido_centavos ?? 0}
            neutro
            className="text-2xl font-bold"
          />
        </Kpi>
        <Kpi
          label="Resultado"
          hint={
            totais.resultado_pct != null
              ? pctTexto(totais.resultado_pct)
              : undefined
          }
        >
          <Valor
            centavos={totais.resultado_centavos ?? 0}
            sinal
            className="text-2xl font-bold"
          />
        </Kpi>
        <Kpi
          label="Rentabilidade (12M)"
          hint={
            visao.data?.vs_cdi_pp != null
              ? `${pctTexto(visao.data.vs_cdi_pp)} p.p. vs CDI`
              : undefined
          }
        >
          <span className="text-2xl font-bold tabular-nums">
            {visao.data?.rentabilidade_12m_pct != null
              ? pctTexto(visao.data.rentabilidade_12m_pct)
              : "—"}
          </span>
        </Kpi>
        <Kpi label="Nº de ativos">
          <span className="text-2xl font-bold tabular-nums">
            {totais.quantidade_ativos}
          </span>
        </Kpi>
      </div>

      {/* Barra: busca + "Mais filtros". */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={busca}
            onChange={(e) => reiniciar(setBusca)(e.target.value)}
            placeholder="Buscar ativo, instituição…"
            className="pl-9"
            aria-label="Buscar ativo"
          />
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className="gap-2">
              <SlidersHorizontal className="size-4" aria-hidden />
              Mais filtros
              {filtrosAtivos > 0 ? (
                <Badge variant="secondary" className="ml-1">
                  {filtrosAtivos}
                </Badge>
              ) : null}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72 space-y-3">
            <Filtro
              rotulo="Instituição"
              valor={filtroInstituicao}
              opcoes={instituicoes.map((i) => ({ valor: i, label: i }))}
              onChange={reiniciar(setFiltroInstituicao)}
            />
            <Filtro
              rotulo="Tipo"
              valor={filtroSubtype}
              opcoes={subtypes.map((s) => ({
                valor: s,
                label: rotuloChave(s),
              }))}
              onChange={reiniciar(setFiltroSubtype)}
            />
            <Button
              variant="ghost"
              size="sm"
              className="w-full"
              disabled={filtrosAtivos === 0}
              onClick={() => {
                setFiltroInstituicao(null)
                setFiltroSubtype(null)
                setPagina(1)
              }}
            >
              Limpar filtros
            </Button>
          </PopoverContent>
        </Popover>
      </div>

      <Card className="gap-0 overflow-hidden py-0">
        {/* Abas de classe: sub-navegação da tabela (variante sublinhada). */}
        {/* overflow-y-hidden + pb-1.5: o sublinhado da aba (after:bottom-[-5px]) vazaria e
            overflow-x-auto promove overflow-y a auto → scroll vertical. Ver ativo-drawer.tsx. */}
        <div className="overflow-x-auto overflow-y-hidden border-b px-3 pt-2 pb-1.5">
          <Tabs value={classe} onValueChange={reiniciar(setClasse)}>
            <TabsList variant="line" className="h-auto justify-start">
              {CLASSES.map((c) => {
                const n = posicoes.filter(c.match).length
                return (
                  <TabsTrigger
                    key={c.id}
                    value={c.id}
                    disabled={n === 0 && c.id !== "todos"}
                  >
                    {c.label}{" "}
                    <span className="ml-1 text-muted-foreground">({n})</span>
                  </TabsTrigger>
                )
              })}
            </TabsList>
          </Tabs>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <Th col="ativo" ordenacao={ordenacao} onSort={ordenarPor}>
                  Ativo
                </Th>
                <Th col="tipo" ordenacao={ordenacao} onSort={ordenarPor}>
                  Tipo
                </Th>
                <Th col="instituicao" ordenacao={ordenacao} onSort={ordenarPor}>
                  Instituição
                </Th>
                <Th
                  col="quantidade"
                  ordenacao={ordenacao}
                  onSort={ordenarPor}
                  numerico
                >
                  Quantidade
                </Th>
                <Th
                  col="preco"
                  ordenacao={ordenacao}
                  onSort={ordenarPor}
                  numerico
                >
                  Preço médio
                </Th>
                <Th
                  col="cotacao"
                  ordenacao={ordenacao}
                  onSort={ordenarPor}
                  numerico
                >
                  Cotação
                </Th>
                <Th
                  col="investido"
                  ordenacao={ordenacao}
                  onSort={ordenarPor}
                  numerico
                >
                  Valor investido
                </Th>
                <Th
                  col="valor"
                  ordenacao={ordenacao}
                  onSort={ordenarPor}
                  numerico
                >
                  Valor atual
                </Th>
                <Th
                  col="resultado"
                  ordenacao={ordenacao}
                  onSort={ordenarPor}
                  numerico
                >
                  Rentabilidade
                </Th>
                <Th
                  col="participacao"
                  ordenacao={ordenacao}
                  onSort={ordenarPor}
                  numerico
                >
                  % Carteira
                </Th>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visiveis.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={10}
                    className="py-10 text-center text-muted-foreground"
                  >
                    Nenhum ativo com esses filtros.
                  </TableCell>
                </TableRow>
              ) : (
                visiveis.map((p) => (
                  <PosicaoLinha
                    key={p.chave}
                    posicao={p}
                    onAbrir={() => setSelecionada(p)}
                  />
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {/* Paginação. */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            Mostrar
            <Select
              value={String(porPagina)}
              onValueChange={(v) => reiniciar(setPorPagina)(Number(v))}
            >
              <SelectTrigger
                size="sm"
                className="w-20"
                aria-label="Itens por página"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[10, 25, 50].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            de {filtradas.length}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              disabled={paginaSegura <= 1}
              onClick={() => setPagina((n) => Math.max(1, n - 1))}
              aria-label="Página anterior"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="text-muted-foreground tabular-nums">
              {paginaSegura} / {totalPaginas}
            </span>
            <Button
              variant="outline"
              size="icon"
              disabled={paginaSegura >= totalPaginas}
              onClick={() => setPagina((n) => Math.min(totalPaginas, n + 1))}
              aria-label="Próxima página"
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      </Card>

      <AtivoDrawer
        posicao={selecionada}
        onOpenChange={(aberto) => !aberto && setSelecionada(null)}
      />
    </div>
  )
}

function Cabecalho() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">Carteira</h1>
        <p className="text-sm text-muted-foreground">
          Veja todos os seus investimentos em um só lugar.
        </p>
      </div>
      <SyncButton />
    </header>
  )
}

function Kpi({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardContent className="space-y-1">
        <p className="truncate text-sm text-muted-foreground">{label}</p>
        <div className="text-foreground [&_*]:text-foreground">{children}</div>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  )
}

function Filtro({
  rotulo,
  valor,
  opcoes,
  onChange,
}: {
  rotulo: string
  valor: string | null
  opcoes: { valor: string; label: string }[]
  onChange: (v: string | null) => void
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium">{rotulo}</p>
      <Select
        value={valor ?? "todos"}
        onValueChange={(v) => onChange(v === "todos" ? null : v)}
      >
        <SelectTrigger size="sm" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="todos">Todas</SelectItem>
          {opcoes.map((o) => (
            <SelectItem key={o.valor} value={o.valor}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function Th({
  col,
  ordenacao,
  onSort,
  numerico = false,
  children,
}: {
  col: SortCol
  ordenacao: { col: SortCol; dir: "asc" | "desc" }
  onSort: (col: SortCol) => void
  numerico?: boolean
  children: React.ReactNode
}) {
  const ativo = ordenacao.col === col
  const Icone = ativo && ordenacao.dir === "asc" ? ChevronUp : ChevronDown
  return (
    <TableHead className={numerico ? "text-right" : undefined}>
      <button
        type="button"
        onClick={() => onSort(col)}
        className={`inline-flex items-center gap-1 hover:text-foreground ${
          numerico ? "flex-row-reverse" : ""
        } ${ativo ? "text-foreground" : ""}`}
      >
        {children}
        <Icone
          className={`size-3.5 ${ativo ? "opacity-100" : "opacity-30"}`}
          aria-hidden
        />
      </button>
    </TableHead>
  )
}

/** Marca preço médio/investido parcial: o banco não trouxe compras > 12 meses. Mostra o valor
 *  conhecido (ou "—") com um ⚠; abrir a linha leva ao drawer p/ completar os aportes. */
function AvisoIncompleto({ valor }: { valor?: string }) {
  return (
    <span
      className="inline-flex items-center justify-end gap-1 tabular-nums"
      title="Cálculo parcial — compras anteriores a 12 meses não vêm do banco. Complete os aportes na posição."
    >
      {valor ?? <span aria-hidden>—</span>}
      <AlertTriangle
        className="size-3.5 text-amber-600 dark:text-amber-500"
        aria-hidden
      />
      <span className="sr-only">cálculo parcial, histórico incompleto</span>
    </span>
  )
}

function PosicaoLinha({
  posicao: p,
  onAbrir,
}: {
  posicao: CarteiraPosicao
  onAbrir: () => void
}) {
  const Icone = ICONE_TIPO[p.subtype ?? p.type] ?? Coins
  return (
    <TableRow
      onClick={onAbrir}
      tabIndex={0}
      role="button"
      aria-label={`Abrir ${p.code ?? p.nome ?? "ativo"}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onAbrir()
        }
      }}
      className="cursor-pointer outline-none focus-visible:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
    >
      <TableCell>
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
          >
            <Icone className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium">{p.code ?? p.nome ?? "—"}</p>
            {p.code && p.nome ? (
              <p className="truncate text-xs text-muted-foreground">{p.nome}</p>
            ) : null}
          </div>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="secondary">{rotuloClasse(p.type, p.subtype)}</Badge>
      </TableCell>
      <TableCell>
        {p.instituicao ? (
          <div className="flex items-center gap-2">
            <AvatarBanco
              nome={p.instituicao}
              logoUrl={p.instituicao_logo_url}
            />
            <span className="truncate text-sm">{p.instituicao}</span>
          </div>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {p.quantidade != null ? fmtQtd.format(p.quantidade) : "—"}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {p.historico_incompleto ? (
          <AvisoIncompleto
            valor={
              p.preco_medio_centavos != null
                ? formatBRL(p.preco_medio_centavos)
                : undefined
            }
          />
        ) : p.preco_medio_centavos != null ? (
          formatBRL(p.preco_medio_centavos)
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {p.cotacao_centavos != null ? formatBRL(p.cotacao_centavos) : "—"}
      </TableCell>
      <TableCell className="text-right">
        {p.historico_incompleto ? (
          <AvisoIncompleto
            valor={
              p.investido_centavos != null
                ? formatBRL(p.investido_centavos)
                : undefined
            }
          />
        ) : p.investido_centavos != null ? (
          <Valor centavos={p.investido_centavos} neutro />
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="text-right">
        <Valor centavos={p.valor_centavos} neutro />
      </TableCell>
      <TableCell className="text-right">
        {p.resultado_centavos != null ? (
          <div className="flex flex-col items-end leading-tight">
            <Valor centavos={p.resultado_centavos} sinal className="text-sm" />
            {p.resultado_pct != null ? (
              <span
                className={`text-xs ${
                  p.resultado_centavos < 0 ? "text-negative" : "text-positive"
                }`}
              >
                {pctTexto(p.resultado_pct)}
              </span>
            ) : null}
          </div>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {p.participacao_pct != null
          ? `${fmtPct.format(p.participacao_pct)}%`
          : "—"}
      </TableCell>
    </TableRow>
  )
}
