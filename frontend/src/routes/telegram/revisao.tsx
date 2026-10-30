import { useEffect, useRef, useState } from "react"
import { useBlocker, useNavigate } from "react-router"
import { toast } from "sonner"
import { CurrencyInput } from "@/components/common/currency-input"
import { Valor } from "@/components/common/valor"
import { AssinaturaSelect } from "@/components/transacoes/assinatura-select"
import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog"
import { api } from "@/lib/api/client"
import { useContas } from "@/lib/api/contas"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"
import {
  useProventosSugeridos,
  valorEfetivoCentavos,
} from "@/lib/api/transacoes"

type Item = components["schemas"]["RevisaoItem"]
type Rascunho = Pick<
  components["schemas"]["RevisaoPreparar"],
  "alteracoes" | "assinatura" | "regra"
>
type Previa = components["schemas"]["RevisaoPrevia"]

export function MiniappRevisao() {
  const navigate = useNavigate()
  const [itens, setItens] = useState<Item[]>([])
  const [cursor, setCursor] = useState<number | null>(null)
  const [indice, setIndice] = useState(0)
  const [rascunhos, setRascunhos] = useState<Record<number, Rascunho>>({})
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState("")
  const [previa, setPrevia] = useState<Previa>()
  const [aplicado, setAplicado] = useState<string | null>(null)
  const contas = useContas()
  const item = itens[indice]
  const temRascunho = Object.keys(rascunhos).length > 0
  const blocker = useBlocker(temRascunho)
  useEffect(() => {
    const antes = (e: BeforeUnloadEvent) => {
      if (temRascunho) e.preventDefault()
    }
    window.addEventListener("beforeunload", antes)
    if (temRascunho) window.Telegram?.WebApp.enableClosingConfirmation()
    else window.Telegram?.WebApp.disableClosingConfirmation()
    return () => {
      window.removeEventListener("beforeunload", antes)
      window.Telegram?.WebApp.disableClosingConfirmation()
    }
  }, [temRascunho])
  useEffect(() => {
    let ativo = true
    void api
      .GET("/api/revisao")
      .then(({ data, error }) => {
        if (!ativo) return
        if (error || !data) {
          setErro(mensagemErro(error, "Não foi possível carregar a revisão."))
          return
        }
        if (!data.items.length) {
          toast.success("Nenhuma transação pendente.")
          navigate("/telegram", { replace: true })
          return
        }
        setItens(data.items)
        setCursor(data.cursor)
      })
      .catch(() => {
        if (ativo) setErro("Falha de conexão. Abra a revisão novamente.")
      })
    return () => {
      ativo = false
    }
  }, [navigate])

  async function proxima() {
    if (indice + 1 < itens.length) {
      setIndice(indice + 1)
      return
    }
    if (cursor !== null) {
      setOcupado(true)
      try {
        const { data, error } = await api.GET("/api/revisao", {
          params: { query: { cursor } },
        })
        if (error || !data)
          throw new Error(
            mensagemErro(error, "Falha ao carregar mais transações.")
          )
        setItens((atual) => [...atual, ...data.items])
        setCursor(data.cursor)
        if (data.items.length) setIndice(indice + 1)
        else setIndice(itens.length)
      } catch (e) {
        setErro((e as Error).message)
      } finally {
        setOcupado(false)
      }
    } else setIndice(itens.length)
  }
  async function aplicar(op: Previa) {
    if (!item) return
    setOcupado(true)
    setErro("")
    setAplicado(op.operacao_id)
    try {
      const { data, error, response } = await api.POST("/api/revisao/aplicar", {
        body: { operacao_id: op.operacao_id },
      })
      if (error || !data) {
        if (response.status >= 400 && response.status < 500) {
          setAplicado(null)
          setPrevia(undefined)
        }
        throw new Error(
          mensagemErro(error, "Falha ao salvar. Seu rascunho foi mantido.")
        )
      }
      setItens((todos) => todos.map((t) => (t.id === data.id ? data : t)))
      setRascunhos((todos) => {
        const copia = { ...todos }
        delete copia[data.id]
        return copia
      })
      setPrevia(undefined)
      setAplicado(null)
      toast.success("Transação revisada.")
      await proxima()
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }
  async function salvar() {
    if (!item || ocupado) return
    if (previa && aplicado === previa.operacao_id) {
      await aplicar(previa)
      return
    }
    setOcupado(true)
    setErro("")
    try {
      const { data, error } = await api.POST("/api/revisao/preparar", {
        body: {
          transacao_id: item.id,
          versao: item.versao,
          ...(rascunhos[item.id] ?? { alteracoes: {} }),
        },
      })
      if (error || !data)
        throw new Error(
          mensagemErro(error, "Não foi possível preparar a revisão.")
        )
      setPrevia(data)
      if (!data.exige_confirmacao) await aplicar(data)
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }
  async function recarregar() {
    if (!item) return
    if (aplicado && previa) {
      await aplicar(previa)
      return
    }
    const { data, error } = await api.GET("/api/revisao/{transacao_id}", {
      params: { path: { transacao_id: item.id } },
    })
    if (error || !data) {
      setErro(mensagemErro(error, "Falha ao recarregar."))
      return
    }
    setItens((todos) => todos.map((t) => (t.id === data.id ? data : t)))
    setPrevia(undefined)
    setAplicado(null)
    setErro("")
    toast.info("Dados atualizados. Confira seu rascunho antes de salvar.")
  }
  const pendentes = itens.filter((t) => !t.revisada)
  useEffect(() => {
    if (
      itens.length &&
      indice === itens.length &&
      cursor === null &&
      !pendentes.length &&
      !temRascunho
    ) {
      toast.success("Revisão concluída.")
      navigate("/telegram", { replace: true })
    }
  }, [itens.length, indice, cursor, pendentes.length, temRascunho, navigate])
  return (
    <main className="space-y-4" aria-busy={ocupado}>
      <h1 className="text-xl font-semibold">Revisar transações</h1>
      {erro ? (
        <div role="alert" className="space-y-2 text-destructive">
          <p>{erro}</p>
          {item ? (
            <Button
              variant="outline"
              onClick={() => void recarregar()}
              disabled={ocupado}
            >
              Recarregar dados
            </Button>
          ) : null}
        </div>
      ) : null}
      {item ? (
        <>
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {indice + 1} de {itens.length}
            {cursor ? "+" : ""} · {item.revisada ? "Já revisada" : "Pendente"}
          </p>
          <Editor
            key={item.id}
            item={item}
            conta={
              contas.data?.find((c) => c.id === item.conta_id)?.nome ??
              `Conta ${item.conta_id}`
            }
            rascunho={rascunhos[item.id] ?? { alteracoes: {} }}
            mudar={(r) => {
              setRascunhos((todos) => ({ ...todos, [item.id]: r }))
              setPrevia(undefined)
              setAplicado(null)
            }}
            anterior={() => {
              if (!ocupado) setIndice(Math.max(0, indice - 1))
            }}
            proxima={() => {
              if (!ocupado) void proxima()
            }}
            ocupado={ocupado || aplicado !== null}
          />
          <div className="sticky bottom-0 flex flex-wrap gap-2 border-t bg-background py-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <Button
              variant="outline"
              disabled={indice === 0 || ocupado}
              onClick={() => setIndice(indice - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="ghost"
              disabled={ocupado}
              onClick={() => void proxima()}
            >
              Pular
            </Button>
            <Button
              className="ml-auto min-h-11"
              disabled={ocupado}
              onClick={() => void salvar()}
            >
              {ocupado ? "Salvando…" : "Salvar e próxima"}
            </Button>
          </div>
        </>
      ) : itens.length ? (
        <div className="space-y-3">
          <p>
            Você chegou ao fim. {pendentes.length} transações puladas continuam
            pendentes.
          </p>
          <Button
            onClick={() => setIndice(itens.findIndex((t) => !t.revisada))}
          >
            Revisar puladas
          </Button>
          <Button variant="outline" onClick={() => setIndice(itens.length - 1)}>
            Anterior
          </Button>
        </div>
      ) : !erro ? (
        <p role="status">Carregando transações…</p>
      ) : null}
      <AlertDialog
        open={!!previa?.exige_confirmacao && aplicado !== previa.operacao_id}
        onOpenChange={(v) => {
          if (!v && !ocupado) setPrevia(undefined)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Conferir efeitos da revisão</AlertDialogTitle>
            <AlertDialogDescription>
              {previa?.efeitos.join(" ")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={ocupado}>Voltar</AlertDialogCancel>
            <AlertDialogAction
              disabled={ocupado}
              onClick={(e) => {
                e.preventDefault()
                if (previa) void aplicar(previa)
              }}
            >
              Confirmar e salvar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={blocker.state === "blocked"}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sair sem salvar?</AlertDialogTitle>
            <AlertDialogDescription>
              Seus rascunhos desta sessão serão descartados.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => blocker.reset?.()}>
              Continuar revisando
            </AlertDialogCancel>
            <AlertDialogAction onClick={() => blocker.proceed?.()}>
              Descartar e sair
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  )
}

function Editor({
  item,
  conta,
  rascunho,
  mudar,
  anterior,
  proxima,
  ocupado,
}: {
  item: Item
  conta: string
  rascunho: Rascunho
  mudar: (r: Rascunho) => void
  anterior: () => void
  proxima: () => void
  ocupado: boolean
}) {
  const t = { ...item, ...rascunho.alteracoes }
  const proventos = useProventosSugeridos(item.id, item.type === "CREDIT")
  const toque = useRef<{ x: number; y: number } | null>(null)
  const alterar = (v: Rascunho["alteracoes"]) =>
    mudar({ ...rascunho, alteracoes: { ...rascunho.alteracoes, ...v } })
  const categoria =
    rascunho.alteracoes.categoria_override_id === undefined
      ? item.categoria_efetiva_id
      : t.categoria_override_id
  return (
    <fieldset disabled={ocupado} className="space-y-5 rounded-xl border p-4">
      <legend className="sr-only">Transação {item.description}</legend>
      <div
        className="touch-pan-y space-y-1 border-b pb-4"
        onTouchStart={(e) => {
          toque.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }
        }}
        onTouchEnd={(e) => {
          if (!toque.current) return
          const dx = e.changedTouches[0].clientX - toque.current.x,
            dy = e.changedTouches[0].clientY - toque.current.y
          if (Math.abs(dx) > 75 && Math.abs(dx) > Math.abs(dy) * 2) {
            if (dx < 0) proxima()
            else anterior()
          }
          toque.current = null
        }}
      >
        <p className="text-2xl font-semibold tabular-nums">
          <Valor
            centavos={
              item.type === "DEBIT"
                ? -Math.abs(valorEfetivoCentavos(item))
                : Math.abs(valorEfetivoCentavos(item))
            }
          />
        </p>
        <p className="font-medium break-words">{item.description}</p>
        <p className="text-sm text-muted-foreground">
          {new Date(item.date).toLocaleDateString("pt-BR", {
            timeZone: "America/Sao_Paulo",
          })}{" "}
          · {conta}
          {item.total_installments
            ? ` · Parcela ${item.installment_number}/${item.total_installments}`
            : ""}
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="descricao-revisao">Descrição própria</Label>
        <Input
          id="descricao-revisao"
          maxLength={255}
          value={t.descricao_usuario ?? ""}
          onChange={(e) => alterar({ descricao_usuario: e.target.value })}
        />
      </div>
      <div className="space-y-2">
        <Label>Categoria</Label>
        <CategoriaSelect
          value={categoria ?? null}
          disabled={!!t.assinatura_id || !!rascunho.assinatura}
          onChange={(v) =>
            mudar({
              ...rascunho,
              alteracoes: {
                ...rascunho.alteracoes,
                categoria_override_id: v,
                categoria_ajustada_usuario: true,
              },
              regra:
                rascunho.regra && v
                  ? { ...rascunho.regra, categoria_id: v }
                  : null,
            })
          }
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="observacoes-revisao">Observações</Label>
        <Textarea
          id="observacoes-revisao"
          maxLength={2000}
          value={t.observacoes ?? ""}
          onChange={(e) => alterar({ observacoes: e.target.value })}
        />
      </div>
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor="transferencia-revisao">
          Transferência entre minhas contas
        </Label>
        <Switch
          id="transferencia-revisao"
          checked={!!t.eh_transferencia}
          onCheckedChange={(v) => alterar({ eh_transferencia: v })}
        />
      </div>
      <div className="space-y-2">
        <Label>Assinatura</Label>
        <AssinaturaSelect
          value={t.assinatura_id ?? null}
          onChange={(v) =>
            alterar({ assinatura_id: v, nao_e_assinatura: false })
          }
        />
        {t.assinatura_id ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => alterar({ assinatura_id: null })}
          >
            Desvincular assinatura
          </Button>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor="nao-assinatura">Não é uma assinatura</Label>
        <Switch
          id="nao-assinatura"
          checked={!!t.nao_e_assinatura}
          onCheckedChange={(v) =>
            alterar({
              nao_e_assinatura: v,
              ...(v ? { assinatura_id: null } : {}),
            })
          }
        />
      </div>
      {item.type === "CREDIT" ? (
        <div className="space-y-2">
          <Label htmlFor="provento-revisao">Provento de investimento</Label>
          <Select
            value={String(t.investimento_transacao_id ?? "nenhum")}
            onValueChange={(v) =>
              alterar({
                investimento_transacao_id: v === "nenhum" ? null : Number(v),
              })
            }
          >
            <SelectTrigger id="provento-revisao">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="nenhum">Sem vínculo</SelectItem>
              {t.investimento_transacao_id &&
              !proventos.data?.some(
                (p) => p.id === t.investimento_transacao_id
              ) ? (
                <SelectItem value={String(t.investimento_transacao_id)}>
                  Provento vinculado #{t.investimento_transacao_id}
                </SelectItem>
              ) : null}
              {proventos.data?.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  #{p.id} · {p.date?.slice(0, 10)} ·{" "}
                  <Valor centavos={p.amount_centavos} />
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {proventos.isError ? (
            <p role="alert">Não foi possível buscar os proventos.</p>
          ) : null}
        </div>
      ) : null}
      <details className="space-y-3">
        <summary className="cursor-pointer py-2 font-medium">
          Criar assinatura ou regra
        </summary>
        <div className="flex items-center justify-between gap-3">
          <Label htmlFor="nova-assinatura">
            Criar assinatura com esta transação
          </Label>
          <Switch
            id="nova-assinatura"
            checked={!!rascunho.assinatura}
            onCheckedChange={(v) =>
              mudar({
                ...rascunho,
                assinatura: v
                  ? {
                      nome:
                        t.descricao_usuario || item.description || "Assinatura",
                      valor_centavos: Math.abs(valorEfetivoCentavos(item)),
                      periodicidade: "mensal",
                      ativa: true,
                      detectada_automaticamente: false,
                      conta_id: item.conta_id,
                      categoria_id: categoria,
                      nomes_transacao: item.description
                        ? [item.description]
                        : [],
                    }
                  : null,
              })
            }
          />
        </div>
        {rascunho.assinatura ? (
          <div className="space-y-3">
            <Label htmlFor="assinatura-nome">Nome da assinatura</Label>
            <Input
              id="assinatura-nome"
              value={rascunho.assinatura.nome}
              onChange={(e) =>
                mudar({
                  ...rascunho,
                  assinatura: { ...rascunho.assinatura!, nome: e.target.value },
                })
              }
            />
            <Label htmlFor="assinatura-valor">Valor</Label>
            <CurrencyInput
              id="assinatura-valor"
              value={rascunho.assinatura.valor_centavos}
              onChange={(v) =>
                mudar({
                  ...rascunho,
                  assinatura: { ...rascunho.assinatura!, valor_centavos: v },
                })
              }
            />
            <Label htmlFor="periodicidade">Periodicidade</Label>
            <Select
              value={rascunho.assinatura.periodicidade}
              onValueChange={(v) =>
                mudar({
                  ...rascunho,
                  assinatura: {
                    ...rascunho.assinatura!,
                    periodicidade: v as NonNullable<
                      Rascunho["assinatura"]
                    >["periodicidade"],
                  },
                })
              }
            >
              <SelectTrigger id="periodicidade">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[
                  "mensal",
                  "trimestral",
                  "semestral",
                  "anual",
                  "irregular",
                ].map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}
        <div className="flex items-center justify-between gap-3">
          <Label htmlFor="nova-regra">
            Criar regra para a categoria escolhida
          </Label>
          <Switch
            id="nova-regra"
            disabled={!categoria}
            checked={!!rascunho.regra}
            onCheckedChange={(v) =>
              mudar({
                ...rascunho,
                regra:
                  v && categoria
                    ? {
                        texto: (item.description ?? "").slice(0, 120),
                        tipo_match: "exato",
                        categoria_id: categoria,
                      }
                    : null,
              })
            }
          />
        </div>
        {rascunho.regra ? (
          <div className="space-y-3">
            <Label htmlFor="regra-texto">Texto da regra</Label>
            <Input
              id="regra-texto"
              minLength={3}
              maxLength={120}
              value={rascunho.regra.texto}
              onChange={(e) =>
                mudar({
                  ...rascunho,
                  regra: { ...rascunho.regra!, texto: e.target.value },
                })
              }
            />
            <Label htmlFor="tipo-regra">Comparação</Label>
            <Select
              value={rascunho.regra.tipo_match}
              onValueChange={(v) =>
                mudar({
                  ...rascunho,
                  regra: {
                    ...rascunho.regra!,
                    tipo_match: v as "exato" | "contem",
                  },
                })
              }
            >
              <SelectTrigger id="tipo-regra">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="exato">Texto exato</SelectItem>
                <SelectItem value="contem">Contém o texto</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ) : null}
        <p className="text-xs text-muted-foreground">
          A criação acontece junto com o salvamento da revisão.
        </p>
      </details>
    </fieldset>
  )
}
