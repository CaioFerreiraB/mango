import { Info, Plus, Receipt, Sparkles, Users } from "lucide-react"
import { useState } from "react"

import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { DivisaoDetalheDialog } from "@/components/divisoes/divisao-detalhe-dialog"
import { NovaDivisaoWizard } from "@/components/divisoes/nova-divisao-wizard"
import { PessoaAvatar } from "@/components/divisoes/pessoa-avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useIsMobile } from "@/hooks/use-mobile"
import { useMe } from "@/lib/api/auth"
import { nomeCategoria, useCategorias } from "@/lib/api/categorias"
import { useConfiguracaoSistema } from "@/lib/api/configuracoes"
import {
  useDivisoes,
  usePessoasDivisao,
  useResumoDivisoes,
  type DivisaoDespesa,
  type EscopoDivisao,
} from "@/lib/api/divisoes"
import { formatDate } from "@/lib/format"

/** Badge/tooltip (§4.11-otimização): avisa que os saldos exibidos já vêm simplificados —
 *  evita estranheza ao ver saldo 0 com alguém que tem despesa em aberto (a dívida foi
 *  "roteada" para outra pessoa). */
function BadgeOtimizado() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="gap-1">
          <Sparkles className="size-3" /> Otimizado
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        Dívidas em cadeia foram combinadas em transferências diretas — não altera nenhum
        lançamento, só como o saldo é exibido.
      </TooltipContent>
    </Tooltip>
  )
}

export function DivisoesPage() {
  const [detalhe, setDetalhe] = useState<number | null>(null)

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Divisão de contas</h1>
          <p className="text-sm text-muted-foreground">
            Acompanhe suas despesas compartilhadas e acertos com amigos.
          </p>
        </div>
        <NovaDivisaoWizard
          trigger={
            <Button>
              <Plus className="size-4" /> Nova divisão
            </Button>
          }
        />
      </header>

      <Tabs defaultValue="resumo">
        <TabsList>
          <TabsTrigger value="resumo">Resumo</TabsTrigger>
          <TabsTrigger value="transacoes">Transações</TabsTrigger>
          <TabsTrigger value="pessoas">Pessoas</TabsTrigger>
        </TabsList>

        <TabsContent value="resumo" className="mt-4">
          <AbaResumo onAbrirDetalhe={setDetalhe} />
        </TabsContent>
        <TabsContent value="transacoes" className="mt-4">
          <AbaTransacoes onAbrirDetalhe={setDetalhe} />
        </TabsContent>
        <TabsContent value="pessoas" className="mt-4">
          <AbaPessoas />
        </TabsContent>
      </Tabs>

      {detalhe !== null ? (
        <DivisaoDetalheDialog id={detalhe} onClose={() => setDetalhe(null)} />
      ) : null}
    </div>
  )
}

function AbaResumo({
  onAbrirDetalhe,
}: {
  onAbrirDetalhe: (id: number) => void
}) {
  const resumo = useResumoDivisoes()
  const pessoas = usePessoasDivisao()
  const recentes = useDivisoes("todas")
  const me = useMe()
  const config = useConfiguracaoSistema()

  if (resumo.isError)
    return <EmptyState title="Não foi possível carregar o resumo" />
  if (resumo.isLoading || !resumo.data) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    )
  }

  const { data } = resumo
  const atividades = [...(recentes.data ?? [])]
    .sort((a, b) => b.atualizado_em.localeCompare(a.atualizado_em))
    .slice(0, 5)
  const pessoasTop = (pessoas.data ?? []).slice(0, 5)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="space-y-1 py-4">
            <p className="text-sm text-muted-foreground">Saldo a receber</p>
            <Valor
              centavos={data.saldo_a_receber_centavos}
              neutro
              className="text-2xl text-positive"
            />
            <p className="text-xs text-muted-foreground">
              de {data.pessoas_a_receber} pessoas
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-1 py-4">
            <p className="text-sm text-muted-foreground">Saldo a pagar</p>
            <Valor
              centavos={data.saldo_a_pagar_centavos}
              absoluto
              neutro
              className="text-2xl text-negative"
            />
            <p className="text-xs text-muted-foreground">
              para {data.pessoas_a_pagar} pessoas
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-1 py-4">
            <p className="text-sm text-muted-foreground">Saldo total</p>
            <Valor
              centavos={data.saldo_total_centavos}
              sinal
              className="text-2xl"
            />
            <p className="text-xs text-muted-foreground">
              {data.saldo_total_centavos >= 0 ? "positivo" : "negativo"}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="space-y-1 py-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Saldos com pessoas</p>
              {config.data?.otimizar_transacoes_divisao ? <BadgeOtimizado /> : null}
            </div>
            {pessoasTop.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Nenhuma pessoa ainda.
              </p>
            ) : (
              <ul className="divide-y">
                {pessoasTop.map((p) => (
                  <li
                    key={p.usuario_id}
                    className="flex items-center gap-3 py-2.5"
                  >
                    <PessoaAvatar nome={p.nome} avatar={p.avatar} />
                    <span className="min-w-0 flex-1 truncate text-sm">
                      {p.nome}
                    </span>
                    <div className="text-right text-xs">
                      <p className="text-muted-foreground">
                        {p.saldo_centavos > 0
                          ? "Você recebe"
                          : p.saldo_centavos < 0
                            ? "Você paga"
                            : "Quitado"}
                      </p>
                      <Valor
                        centavos={p.saldo_centavos}
                        absoluto
                        className="text-sm"
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-1 py-4">
            <p className="text-sm font-medium">Atividades recentes</p>
            {atividades.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Nenhuma divisão ainda.
              </p>
            ) : (
              <ul className="divide-y">
                {atividades.map((d) => (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => onAbrirDetalhe(d.id)}
                      className="flex w-full items-center gap-3 py-2.5 text-left hover:opacity-80"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm">
                          {d.descricao || "Sem descrição"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {d.pago_por_usuario_id === me.data?.id
                            ? "Você pagou"
                            : "Pagou"}{" "}
                          · {formatDate(d.criado_em)}
                        </p>
                      </div>
                      <Valor
                        centavos={d.valor_total_centavos}
                        neutro
                        className="text-sm"
                      />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-2 rounded-lg bg-muted/50 p-3 text-sm">
        <Info className="size-4 shrink-0 text-primary" aria-hidden />
        <p className="text-muted-foreground">
          Divida despesas com amigos que também usam esta instância. Apenas
          usuários cadastrados podem participar das divisões.
        </p>
      </div>
    </div>
  )
}

const ESCOPOS: { value: EscopoDivisao; label: string }[] = [
  { value: "todas", label: "Todas" },
  { value: "minhas", label: "Minhas divisões" },
  { value: "comigo", label: "Comigo" },
  { value: "arquivadas", label: "Arquivadas" },
]

function AbaTransacoes({
  onAbrirDetalhe,
}: {
  onAbrirDetalhe: (id: number) => void
}) {
  const [escopo, setEscopo] = useState<EscopoDivisao>("todas")
  const divisoes = useDivisoes(escopo)
  const isMobile = useIsMobile()
  const me = useMe()
  const categorias = useCategorias()
  const nomesCategoria = new Map(
    (categorias.data ?? []).map((c) => [c.pluggy_id, nomeCategoria(c)])
  )

  return (
    <div className="space-y-3">
      <Tabs value={escopo} onValueChange={(v) => setEscopo(v as EscopoDivisao)}>
        <TabsList>
          {ESCOPOS.map((e) => (
            <TabsTrigger key={e.value} value={e.value}>
              {e.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {divisoes.isError ? (
        <EmptyState title="Não foi possível carregar as divisões" />
      ) : divisoes.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (divisoes.data ?? []).length === 0 ? (
        <EmptyState
          icon={Receipt}
          title="Nenhuma divisão aqui"
          description="Crie uma nova divisão de conta pra começar a acompanhar."
        />
      ) : isMobile ? (
        <div className="divide-y rounded-lg border">
          {(divisoes.data ?? []).map((d) => (
            <LinhaDivisaoMobile
              key={d.id}
              divisao={d}
              meuId={me.data?.id}
              onClick={() => onAbrirDetalhe(d.id)}
            />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Descrição</TableHead>
                <TableHead>Data</TableHead>
                <TableHead className="text-right">Valor total</TableHead>
                <TableHead>Pago por</TableHead>
                <TableHead>Divisão</TableHead>
                <TableHead className="text-right">Meu saldo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(divisoes.data ?? []).map((d) => (
                <TableRow
                  key={d.id}
                  className="cursor-pointer"
                  onClick={() => onAbrirDetalhe(d.id)}
                >
                  <TableCell>
                    <p>{d.descricao || "Sem descrição"}</p>
                    <p className="text-xs text-muted-foreground">
                      {d.categoria_id
                        ? (nomesCategoria.get(d.categoria_id) ?? d.categoria_id)
                        : "Sem categoria"}
                    </p>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(d.criado_em)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Valor centavos={d.valor_total_centavos} neutro />
                  </TableCell>
                  <TableCell>
                    {d.pago_por_usuario_id === me.data?.id
                      ? "Você"
                      : nomePagador(d)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      {d.modo_divisao === "igualmente"
                        ? "Igualmente"
                        : "Integral"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Valor centavos={d.meu_saldo_centavos} sinal />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

function nomePagador(d: DivisaoDespesa): string {
  return (
    d.participantes.find((p) => p.usuario_id === d.pago_por_usuario_id)?.nome ??
    "Outra pessoa"
  )
}

function LinhaDivisaoMobile({
  divisao,
  meuId,
  onClick,
}: {
  divisao: DivisaoDespesa
  meuId: number | undefined
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 p-3 text-left"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">
          {divisao.descricao || "Sem descrição"}
        </p>
        <p className="text-xs text-muted-foreground">
          {divisao.pago_por_usuario_id === meuId
            ? "Você pagou"
            : `${nomePagador(divisao)} pagou`}{" "}
          · {formatDate(divisao.criado_em)}
        </p>
      </div>
      <div className="text-right">
        <Valor
          centavos={divisao.valor_total_centavos}
          neutro
          className="text-sm"
        />
        <Valor
          centavos={divisao.meu_saldo_centavos}
          sinal
          className="text-xs"
        />
      </div>
    </button>
  )
}

function AbaPessoas() {
  const pessoas = usePessoasDivisao()
  const config = useConfiguracaoSistema()

  return (
    <div className="space-y-3">
      {config.data?.otimizar_transacoes_divisao ? (
        <div className="flex justify-end">
          <BadgeOtimizado />
        </div>
      ) : null}
      {pessoas.isError ? (
        <EmptyState title="Não foi possível carregar as pessoas" />
      ) : pessoas.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (pessoas.data ?? []).length === 0 ? (
        <EmptyState
          icon={Users}
          title="Nenhuma pessoa ainda"
          description="Crie uma divisão de conta com outra pessoa, ou peça pro administrador criar um usuário pra ela em Configurações."
        />
      ) : (
        <div className="divide-y rounded-lg border">
          {(pessoas.data ?? []).map((p) => (
            <div key={p.usuario_id} className="flex items-center gap-3 p-3">
              <PessoaAvatar nome={p.nome} avatar={p.avatar} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{p.nome}</p>
                <Badge
                  variant={p.status === "usuario" ? "secondary" : "outline"}
                  className="mt-0.5"
                >
                  {p.status === "usuario" ? "Usuário" : "Usuário (só divisão)"}
                </Badge>
              </div>
              <div className="text-right text-sm">
                <p className="text-xs text-muted-foreground">
                  {p.saldo_centavos > 0
                    ? "Você recebe"
                    : p.saldo_centavos < 0
                      ? "Você paga"
                      : "Quitado"}
                </p>
                <Valor centavos={p.saldo_centavos} absoluto />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
