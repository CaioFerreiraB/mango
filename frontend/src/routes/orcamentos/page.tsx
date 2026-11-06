import {
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  PiggyBank,
  Settings2,
  Wand2,
  X,
  type LucideIcon,
} from "lucide-react"
import { createElement, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { AnelProgresso } from "@/components/common/anel-progresso"
import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { ConfigurarOrcamentoPadraoDialog } from "@/components/orcamentos/configurar-orcamento-padrao-dialog"
import { EditarMesDialog } from "@/components/orcamentos/editar-mes-dialog"
import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useIsMobile } from "@/hooks/use-mobile"
import { useIconeCategoria } from "@/lib/api/categoria-icones"
import { useMapaCategorias } from "@/lib/api/categorias"
import {
  useConsumoOrcamentos,
  useMaterializarMes,
  useTransacoesDoOrcamento,
  type AlvoDrilldown,
  type OrcamentoConsumoItem,
} from "@/lib/api/orcamentos"
import { formatMesAno, hojeISO } from "@/lib/format"
import { cn } from "@/lib/utils"

// Escala de "calor" do consumo — a cor nunca é o único sinal (o % e a barra também informam).
// Só se aplica à despesa: receita não tem conceito de "estourar".
function corAlerta(alerta: number | null): string {
  if (alerta === null) return "bg-primary"
  if (alerta >= 100) return "bg-red-600"
  if (alerta >= 90) return "bg-orange-600"
  if (alerta >= 75) return "bg-orange-500"
  return "bg-yellow-500"
}

export function OrcamentosPage() {
  const hoje = hojeISO()
  const anoAtual = Number(hoje.slice(0, 4))
  const mesAtual = Number(hoje.slice(5, 7))
  const [ano, setAno] = useState(anoAtual)
  const [mes, setMes] = useState(mesAtual)
  // Linha cujas transações estão abertas (uma por vez na página); fecha ao trocar de mês.
  const [alvo, setAlvo] = useState<AlvoDrilldown | null>(null)
  const consumo = useConsumoOrcamentos(ano, mes)
  const noMesAtual = ano === anoAtual && mes === mesAtual
  const mesEhPassado = ano < anoAtual || (ano === anoAtual && mes < mesAtual)

  function mudarMes(delta: number) {
    const total = ano * 12 + (mes - 1) + delta
    setAno(Math.floor(total / 12))
    setMes((total % 12) + 1)
    setAlvo(null)
  }

  const rotuloMes = formatMesAno(`${ano}-${String(mes).padStart(2, "0")}-01`)
  // `itens` inclui linhas suprimidas (removidas só deste mês) — só "Editar mês" precisa delas
  // (pra oferecer "restaurar"); a Visão Geral (resumo + tabela) as esconde.
  const itens = consumo.data?.itens ?? []
  const visiveis = itens.filter((i) => !i.suprimido)
  const despesas = visiveis.filter((i) => i.tipo === "despesa")
  const receitas = visiveis.filter((i) => i.tipo === "receita")
  const secao = { ano, mes, rotuloMes, alvo, onAlvo: setAlvo }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Orçamento</h1>
          <p className="text-sm text-muted-foreground">
            Limite mensal por categoria, com alertas em 50%, 75%, 90% e 100%.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 rounded-md border p-0.5">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => mudarMes(-1)}
              aria-label="Mês anterior"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-36 text-center text-sm font-medium capitalize">
              {rotuloMes}
            </span>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => mudarMes(1)}
              disabled={noMesAtual}
              aria-label="Próximo mês"
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
          <EditarMesDialog
            itens={itens}
            ano={ano}
            mes={mes}
            disabled={itens.length === 0}
          />
          {/* No mobile o botão reaparece embaixo da lista de categorias — aqui não cabe junto
              do seletor de mês sem quebrar a linha de forma feia. */}
          <div className="hidden sm:block">
            <ConfigurarOrcamentoPadraoDialog />
          </div>
        </div>
      </header>

      {consumo.isError ? (
        <EmptyState title="Não foi possível carregar os orçamentos" />
      ) : consumo.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : visiveis.length === 0 ? (
        mesEhPassado ? (
          <EmptyState
            icon={PiggyBank}
            title="Nenhum orçamento neste mês"
            description="Meses passados não recebem orçamento automaticamente. Aplique o orçamento padrão a este mês, ou configure um orçamento específico só pra ele."
          >
            <div className="flex flex-wrap justify-center gap-2">
              <AplicarPadraoBotao ano={ano} mes={mes} />
              <EditarMesDialog
                itens={itens}
                ano={ano}
                mes={mes}
                trigger={
                  <Button variant="outline">
                    <Settings2 className="size-4" /> Configurar orçamento do mês
                  </Button>
                }
              />
            </div>
          </EmptyState>
        ) : (
          <EmptyState
            icon={PiggyBank}
            title="Nenhum orçamento neste mês"
            description="Defina um orçamento padrão pra que ele passe a valer todo mês, a partir de agora."
          >
            <ConfigurarOrcamentoPadraoDialog />
          </EmptyState>
        )
      ) : (
        <div className="space-y-8">
          <SecaoOrcamento
            tipo="despesa"
            titulo="Despesas"
            itens={despesas}
            naoPlanejado={consumo.data?.nao_planejado_despesa_centavos ?? 0}
            {...secao}
          />
          <SecaoOrcamento
            tipo="receita"
            titulo="Receitas"
            itens={receitas}
            naoPlanejado={consumo.data?.nao_planejado_receita_centavos ?? 0}
            {...secao}
          />
          <ConfigurarOrcamentoPadraoDialog
            trigger={
              <Button variant="outline" className="w-full sm:hidden">
                <Settings2 className="size-4" /> Configurar orçamento padrão
              </Button>
            }
          />
        </div>
      )}
    </div>
  )
}

/** Aplica o orçamento padrão a um mês específico sob pedido (a materialização automática só
 *  cobre o mês corrente) — pro caso de um mês passado sem nada configurado. */
function AplicarPadraoBotao({ ano, mes }: { ano: number; mes: number }) {
  const materializar = useMaterializarMes()
  return (
    <Button
      onClick={() =>
        materializar.mutate(
          { ano, mes },
          {
            onSuccess: () =>
              toast.success("Orçamento padrão aplicado a este mês."),
            onError: (err) => toast.error(err.message),
          }
        )
      }
      disabled={materializar.isPending}
    >
      <Wand2 className="size-4" /> Adicionar orçamento padrão
    </Button>
  )
}

/** Linha da Visão Geral — uma categoria orçada ou o "Não planejado" (`categoriaId: null`, sem
 *  limite: orçado/restante "—" e % sempre 100). */
type LinhaVisao = {
  key: string
  categoriaId: string | null
  nome: string
  icone: LucideIcon
  limite: number | null
  realizado: number
  percentual: number
  cor: string
}

function SecaoOrcamento({
  tipo,
  titulo,
  itens,
  naoPlanejado,
  ano,
  mes,
  rotuloMes,
  alvo,
  onAlvo,
}: {
  tipo: "despesa" | "receita"
  titulo: string
  itens: OrcamentoConsumoItem[]
  naoPlanejado: number
  ano: number
  mes: number
  rotuloMes: string
  alvo: AlvoDrilldown | null
  onAlvo: (alvo: AlvoDrilldown | null) => void
}) {
  const nomes = useMapaCategorias()
  const iconeCategoria = useIconeCategoria()
  const isMobile = useIsMobile()
  if (itens.length === 0 && naoPlanejado === 0) return null

  const despesa = tipo === "despesa"
  const linhas: LinhaVisao[] = itens.map((item) => ({
    key: String(item.orcamento_mensal_id),
    categoriaId: item.categoria_id,
    nome: nomes.get(item.categoria_id) ?? item.categoria_id,
    icone: iconeCategoria(item.categoria_id),
    limite: item.limite_centavos,
    realizado: item.realizado_centavos,
    percentual: item.percentual,
    cor: despesa ? corAlerta(item.alerta_atingido) : "bg-primary",
  }))
  if (naoPlanejado > 0)
    linhas.push({
      key: "nao-planejado",
      categoriaId: null,
      nome: "Não planejado",
      icone: CircleDashed,
      limite: null,
      realizado: naoPlanejado,
      percentual: 100, // sem orçado: por definição tudo está "fora" do planejado
      cor: "bg-muted-foreground",
    })

  const totalOrcado = itens.reduce((acc, i) => acc + i.limite_centavos, 0)
  // O não planejado entra no realizado: o resumo reflete tudo o que saiu/entrou no mês.
  const totalRealizado = linhas.reduce((acc, l) => acc + l.realizado, 0)
  const restanteTotal = totalOrcado - totalRealizado
  const percentualTotal =
    totalOrcado > 0
      ? Math.round((totalRealizado / totalOrcado) * 100)
      : totalRealizado > 0
        ? 100
        : 0

  const abertaKey =
    alvo?.tipo === tipo
      ? (linhas.find((l) => l.categoriaId === alvo.categoriaId)?.key ?? null)
      : null
  const aberta = linhas.find((l) => l.key === abertaKey) ?? null
  function alternar(linha: LinhaVisao) {
    onAlvo(
      linha.key === abertaKey ? null : { tipo, categoriaId: linha.categoriaId }
    )
  }

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">{titulo}</h2>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-6 py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:gap-8">
            <div>
              <p className="text-sm text-muted-foreground">
                {despesa ? "Total orçado" : "Meta total"}
              </p>
              <p className="text-lg font-semibold">
                <Valor centavos={totalOrcado} neutro />
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                {despesa ? "Gasto até agora" : "Recebido até agora"}
              </p>
              <p className="text-lg font-semibold">
                <Valor centavos={totalRealizado} neutro />
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                {despesa ? "Restante" : "Restante pra meta"}
              </p>
              <p className="text-lg font-semibold">
                {/* Nunca mostra "-": despesa mantém a cor do sinal real (vermelho se estourou),
                    só sem o sinal de menos no texto; receita usa o valor já em módulo — bater
                    ou passar da meta é notícia boa, nunca um alerta. */}
                <Valor
                  centavos={despesa ? restanteTotal : Math.abs(restanteTotal)}
                  absoluto={despesa}
                />
              </p>
            </div>
          </div>
          <AnelProgresso
            pct={percentualTotal}
            tamanho={96}
            rotulo={despesa ? "utilizado" : "recebido"}
          />
        </CardContent>
      </Card>

      {isMobile ? (
        <div className="divide-y rounded-lg border">
          {linhas.map((linha) => (
            <button
              key={linha.key}
              type="button"
              onClick={() => alternar(linha)}
              aria-expanded={linha.key === abertaKey}
              className={cn(
                "flex w-full items-center gap-3 p-3 text-left outline-none focus-visible:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring",
                linha.key === abertaKey && "bg-muted/60"
              )}
            >
              {createElement(linha.icone, {
                className: "size-4 shrink-0 text-muted-foreground",
                "aria-hidden": true,
              })}
              <span className="min-w-0 flex-1 space-y-1.5">
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">
                    {linha.nome}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                    {linha.percentual}%
                  </span>
                </span>
                <span className="block text-xs text-muted-foreground">
                  <Valor
                    centavos={linha.realizado}
                    neutro
                    className="text-xs font-normal"
                  />{" "}
                  {linha.limite === null ? (
                    "fora do orçamento"
                  ) : (
                    <>
                      de{" "}
                      <Valor
                        centavos={linha.limite}
                        neutro
                        className="text-xs font-normal"
                      />
                    </>
                  )}
                </span>
                <Progress
                  value={Math.min(linha.percentual, 100)}
                  indicatorClassName={linha.cor}
                />
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Categoria</TableHead>
                <TableHead className="text-right">
                  {despesa ? "Orçado" : "Meta"}
                </TableHead>
                <TableHead className="text-right">
                  {despesa ? "Gasto" : "Recebido"}
                </TableHead>
                <TableHead className="text-right">Restante</TableHead>
                <TableHead className="w-36">%</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {linhas.map((linha) => {
                const restante =
                  linha.limite === null ? null : linha.limite - linha.realizado
                return (
                  <TableRow
                    key={linha.key}
                    onClick={() => alternar(linha)}
                    data-state={
                      linha.key === abertaKey ? "selected" : undefined
                    }
                    className="cursor-pointer"
                  >
                    <TableCell>
                      {/* O botão é o alvo acessível (teclado/leitor de tela); o clique na linha
                          inteira é só conveniência de mouse. */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          alternar(linha)
                        }}
                        aria-expanded={linha.key === abertaKey}
                        className="flex max-w-full items-center gap-2 rounded-sm text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {createElement(linha.icone, {
                          className: "size-4 shrink-0 text-muted-foreground",
                          "aria-hidden": true,
                        })}
                        <span className="truncate">{linha.nome}</span>
                      </button>
                    </TableCell>
                    <TableCell className="text-right">
                      {linha.limite === null ? (
                        <SemValor />
                      ) : (
                        <Valor centavos={linha.limite} neutro />
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Valor centavos={linha.realizado} neutro />
                    </TableCell>
                    <TableCell className="text-right">
                      {restante === null ? (
                        <SemValor />
                      ) : (
                        <Valor
                          centavos={despesa ? restante : Math.abs(restante)}
                          absoluto={despesa}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={Math.min(linha.percentual, 100)}
                          indicatorClassName={linha.cor}
                          className="w-16"
                        />
                        <span className="text-xs text-muted-foreground tabular-nums">
                          {linha.percentual}%
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {aberta && alvo && (
        <PainelTransacoes
          ano={ano}
          mes={mes}
          alvo={alvo}
          titulo={`${aberta.nome} · ${rotuloMes}`}
          onFechar={() => onAlvo(null)}
        />
      )}
    </section>
  )
}

function SemValor() {
  return (
    <span className="text-muted-foreground" aria-label="sem orçado">
      —
    </span>
  )
}

/** Transações da linha aberta, logo abaixo da tabela da seção — mesma tabela/drawer da tela de
 *  Transações (recategorizar aqui já atualiza o consumo). */
function PainelTransacoes({
  ano,
  mes,
  alvo,
  titulo,
  onFechar,
}: {
  ano: number
  mes: number
  alvo: AlvoDrilldown
  titulo: string
  onFechar: () => void
}) {
  const transacoes = useTransacoesDoOrcamento(ano, mes, alvo)
  const ref = useRef<HTMLElement>(null)
  // Traz o painel pra vista ao abrir/trocar de linha — numa tabela longa ele nasceria fora da tela.
  useEffect(() => {
    ref.current?.scrollIntoView({ block: "nearest" })
  }, [alvo.tipo, alvo.categoriaId])

  return (
    <section
      ref={ref}
      aria-label={`Transações de ${titulo}`}
      className="space-y-3 rounded-lg border p-3 sm:p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">
          <span className="text-muted-foreground">Transações · </span>
          {titulo}
        </h3>
        <Button
          variant="ghost"
          size="icon"
          onClick={onFechar}
          aria-label="Fechar transações"
        >
          <X className="size-4" />
        </Button>
      </div>
      {transacoes.isError ? (
        <EmptyState title="Não foi possível carregar as transações" />
      ) : transacoes.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : (transacoes.data ?? []).length === 0 ? (
        <EmptyState title="Nenhuma transação nesta categoria no mês" />
      ) : (
        <TransacoesTabela items={transacoes.data!} />
      )}
    </section>
  )
}
