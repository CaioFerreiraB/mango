import { Pencil } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { CurrencyInput } from "@/components/common/currency-input"
import { Valor } from "@/components/common/valor"
import { PessoaAvatar } from "@/components/divisoes/pessoa-avatar"
import {
  PessoaMultiPicker,
  type PessoaSelecionada,
} from "@/components/divisoes/pessoa-multi-picker"
import { PessoaSelect } from "@/components/divisoes/pessoa-select"
import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { useMe } from "@/lib/api/auth"
import { nomeCategoria, useCategorias } from "@/lib/api/categorias"
import {
  useAtualizarDivisao,
  useDefinirVinculo,
  useDivisao,
  useExcluirDivisao,
  useTransacoesCandidatas,
  type DivisaoDespesa,
  type ModoDivisao,
} from "@/lib/api/divisoes"
import { descricaoExibida, valorEfetivoCentavos } from "@/lib/api/transacoes"
import { formatBRL, formatDate } from "@/lib/format"

export function DivisaoDetalheDialog({
  id,
  onClose,
}: {
  id: number
  onClose: () => void
}) {
  const { data, isLoading } = useDivisao(id)
  const [editando, setEditando] = useState(false)

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
        {isLoading || !data ? (
          <Skeleton className="h-64 w-full" />
        ) : editando ? (
          <DivisaoEditarForm
            divisao={data}
            onCancelar={() => setEditando(false)}
            onSalvar={() => setEditando(false)}
          />
        ) : (
          <DivisaoVisao
            divisao={data}
            onEditar={() => setEditando(true)}
            onExcluir={onClose}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function DivisaoVisao({
  divisao,
  onEditar,
  onExcluir,
}: {
  divisao: DivisaoDespesa
  onEditar: () => void
  onExcluir: () => void
}) {
  const me = useMe()
  const excluir = useExcluirDivisao()
  const categorias = useCategorias()
  const categoria = (categorias.data ?? []).find(
    (c) => c.pluggy_id === divisao.categoria_id
  )
  const souCriador = me.data?.id === divisao.criado_por_usuario_id

  function confirmarExclusao() {
    excluir.mutate(divisao.id, {
      onSuccess: () => {
        toast.success("Divisão excluída.")
        onExcluir()
      },
      onError: (err) => toast.error(err.message),
    })
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Detalhes da divisão</DialogTitle>
      </DialogHeader>

      <div className="space-y-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-medium">
              {divisao.descricao || "Sem descrição"}
            </p>
            <p className="text-xs text-muted-foreground">
              {categoria ? nomeCategoria(categoria) : "Sem categoria"} ·{" "}
              {formatDate(divisao.data)}
            </p>
          </div>
          <Valor
            centavos={divisao.valor_total_centavos}
            neutro
            className="text-lg"
          />
        </div>

        <Badge variant="secondary">
          {divisao.modo_divisao === "igualmente"
            ? "Dividir igualmente"
            : "Valor integral"}
        </Badge>

        {/* Conta "somente divisão" não tem transações de banco para vincular. */}
        {me.data?.id === divisao.pago_por_usuario_id &&
        me.data?.tipo === "completo" ? (
          <VinculoTransacao divisao={divisao} />
        ) : null}

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">
            Participantes ({divisao.participantes.length})
          </Label>
          <ul className="divide-y rounded-lg border">
            {divisao.participantes.map((p) => {
              const pagou = p.usuario_id === divisao.pago_por_usuario_id
              return (
                <li
                  key={p.usuario_id}
                  className="flex items-center gap-3 p-2.5"
                >
                  <PessoaAvatar
                    nome={p.nome}
                    avatar={p.avatar}
                    className="size-8"
                  />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {p.usuario_id === me.data?.id ? `Você (${p.nome})` : p.nome}
                  </span>
                  <div className="text-right text-sm">
                    <p className={pagou ? "text-positive" : "text-negative"}>
                      {pagou ? "Pagou" : "Deve"}
                    </p>
                    <Valor
                      centavos={p.valor_centavos}
                      neutro
                      className="text-sm"
                    />
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      </div>

      <DialogFooter className="justify-between sm:justify-between">
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="outline"
              className="text-destructive"
              disabled={!souCriador}
            >
              Excluir
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Excluir divisão</AlertDialogTitle>
              <AlertDialogDescription>
                Tem certeza que deseja excluir "
                {divisao.descricao || "esta divisão"}"? Esta ação não pode ser
                desfeita.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction
                className={buttonVariants({ variant: "destructive" })}
                onClick={confirmarExclusao}
              >
                Excluir
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <Button onClick={onEditar} disabled={!souCriador}>
          <Pencil className="size-4" /> Editar
        </Button>
      </DialogFooter>
    </>
  )
}

/** Para quem pagou: a transação do banco que corresponde à despesa (RF02). Sem ela a divisão fica
 *  pendente de revisão; "fora do banco" encerra a pendência e conta a sua parte no orçamento. */
function VinculoTransacao({ divisao }: { divisao: DivisaoDespesa }) {
  const vinculo = useDefinirVinculo()
  const [escolhendo, setEscolhendo] = useState(false)
  const candidatas = useTransacoesCandidatas(
    divisao.valor_total_centavos,
    divisao.data,
    escolhendo
  )
  const definir = (
    corpo: { transacao_id?: number | null; sem_transacao: boolean },
    msg: string
  ) =>
    vinculo.mutate(
      { id: divisao.id, vinculo: corpo },
      {
        onSuccess: () => {
          toast.success(msg)
          setEscolhendo(false)
        },
        onError: (err) => toast.error(err.message),
      }
    )

  const estado =
    divisao.transacao_id !== null
      ? "Vinculada a uma transação — no orçamento conta só a sua parte."
      : divisao.sem_transacao
        ? "Paga fora do banco — sua parte conta no orçamento."
        : "Sem transação vinculada — pendente de revisão."

  return (
    <div className="space-y-2 rounded-lg border p-3 text-sm">
      <p className="font-medium">Transação do banco</p>
      <p className="text-xs text-muted-foreground">{estado}</p>
      {escolhendo ? (
        candidatas.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : candidatas.isError ? (
          <p role="alert" className="text-xs text-destructive">
            Não foi possível buscar as transações.{" "}
            <button
              type="button"
              className="underline underline-offset-4"
              onClick={() => candidatas.refetch()}
            >
              Tentar de novo
            </button>
          </p>
        ) : (candidatas.data ?? []).length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Nenhuma saída sem divisão em 7 dias dessa data.
          </p>
        ) : (
          <ul
            className="max-h-48 divide-y overflow-y-auto rounded-md border"
            aria-label="Transações candidatas"
          >
            {(candidatas.data ?? []).map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  disabled={vinculo.isPending}
                  onClick={() =>
                    definir(
                      { transacao_id: t.id, sem_transacao: false },
                      "Transação vinculada."
                    )
                  }
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-muted/40"
                >
                  <span className="min-w-0">
                    <span className="block truncate">
                      {descricaoExibida(t) ?? "—"}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(t.date)}
                    </span>
                  </span>
                  <span className="shrink-0 tabular-nums">
                    {formatBRL(Math.abs(valorEfetivoCentavos(t)))}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )
      ) : null}
      <div className="flex flex-wrap gap-1">
        {divisao.transacao_id === null && !escolhendo ? (
          <Button
            size="xs"
            variant="secondary"
            onClick={() => setEscolhendo(true)}
          >
            Vincular transação
          </Button>
        ) : null}
        {divisao.transacao_id !== null || divisao.sem_transacao ? (
          <Button
            size="xs"
            variant="ghost"
            disabled={vinculo.isPending}
            onClick={() =>
              definir(
                { sem_transacao: false },
                "Divisão pendente de transação."
              )
            }
          >
            {divisao.transacao_id !== null ? "Desvincular" : "Desfazer"}
          </Button>
        ) : (
          <Button
            size="xs"
            variant="ghost"
            disabled={vinculo.isPending}
            onClick={() =>
              definir(
                { sem_transacao: true },
                "Marcada como paga fora do banco."
              )
            }
          >
            Paguei fora do banco
          </Button>
        )}
      </div>
    </div>
  )
}

function DivisaoEditarForm({
  divisao,
  onCancelar,
  onSalvar,
}: {
  divisao: DivisaoDespesa
  onCancelar: () => void
  onSalvar: () => void
}) {
  const [descricao, setDescricao] = useState(divisao.descricao ?? "")
  const [categoriaId, setCategoriaId] = useState<string | null>(
    divisao.categoria_id
  )
  const [valor, setValor] = useState(divisao.valor_total_centavos)
  const [modo, setModo] = useState<ModoDivisao>(
    divisao.modo_divisao as ModoDivisao
  )
  const [pagador, setPagador] = useState<PessoaSelecionada | null>(() => {
    const linha = divisao.participantes.find(
      (p) => p.usuario_id === divisao.pago_por_usuario_id
    )
    return {
      id: divisao.pago_por_usuario_id,
      nome: linha?.nome ?? "Pagador",
      avatar: linha?.avatar ?? null,
    }
  })
  const [participantes, setParticipantes] = useState<PessoaSelecionada[]>(() =>
    divisao.participantes
      .filter((p) => p.usuario_id !== divisao.pago_por_usuario_id)
      .map((p) => ({ id: p.usuario_id, nome: p.nome, avatar: p.avatar }))
  )
  const [devedor, setDevedor] = useState<PessoaSelecionada | null>(() =>
    divisao.modo_divisao === "integral" ? (participantes[0] ?? null) : null
  )
  const atualizar = useAtualizarDivisao()
  const me = useMe()
  // A busca de pessoas nunca devolve quem está logado — injetada à parte pra aparecer na lista
  // de participantes (mesma ideia de `nova-divisao-wizard.tsx`).
  const pessoaEu: PessoaSelecionada | null = me.data
    ? { id: me.data.id, nome: me.data.nome, avatar: me.data.avatar ?? null }
    : null

  function salvar() {
    if (!pagador) return
    const listaParticipantes =
      modo === "integral"
        ? devedor
          ? [devedor.id]
          : []
        : participantes.map((p) => p.id)
    atualizar.mutate(
      {
        id: divisao.id,
        patch: {
          descricao: descricao || null,
          categoria_id: categoriaId,
          valor_total_centavos: valor,
          pago_por_usuario_id: pagador.id,
          modo_divisao: modo,
          participantes: listaParticipantes,
        },
      },
      {
        onSuccess: () => {
          toast.success("Divisão atualizada.")
          onSalvar()
        },
        onError: (err) => toast.error(err.message),
      }
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Editar divisão</DialogTitle>
      </DialogHeader>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="descricao">Descrição</Label>
          <Input
            id="descricao"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Categoria</Label>
          <CategoriaSelect value={categoriaId} onChange={setCategoriaId} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="valor">Valor total</Label>
          <CurrencyInput id="valor" value={valor} onChange={setValor} />
        </div>
        <div className="space-y-1.5">
          <Label>Pago por</Label>
          <PessoaSelect value={pagador} onChange={setPagador} />
        </div>
        <div className="space-y-1.5">
          <Label>Divisão</Label>
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant={modo === "igualmente" ? "default" : "outline"}
              onClick={() => setModo("igualmente")}
            >
              Dividir igualmente
            </Button>
            <Button
              type="button"
              variant={modo === "integral" ? "default" : "outline"}
              onClick={() => setModo("integral")}
            >
              Valor integral
            </Button>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label>Participantes</Label>
          {modo === "igualmente" ? (
            <PessoaMultiPicker
              value={participantes}
              onChange={setParticipantes}
              excluir={pagador ? [pagador.id] : []}
              eu={pessoaEu}
            />
          ) : (
            <PessoaSelect
              value={devedor}
              onChange={setDevedor}
              excluir={pagador ? [pagador.id] : []}
            />
          )}
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onCancelar}>
          Cancelar
        </Button>
        <Button onClick={salvar} disabled={atualizar.isPending}>
          Salvar alterações
        </Button>
      </DialogFooter>
    </>
  )
}
