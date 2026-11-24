import {
  Banknote,
  CalendarClock,
  Coins,
  Divide,
  Landmark,
  Percent,
  User,
  Users,
} from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { CurrencyInput } from "@/components/common/currency-input"
import { Valor } from "@/components/common/valor"
import { EscolhaReajuste } from "@/components/divisoes/escolha-reajuste"
import { OpcaoCard } from "@/components/divisoes/opcao-card"
import { PartesEditor } from "@/components/divisoes/partes-editor"
import {
  PessoaMultiPicker,
  type PessoaSelecionada,
} from "@/components/divisoes/pessoa-multi-picker"
import { PessoaSelect } from "@/components/divisoes/pessoa-select"
import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useMe } from "@/lib/api/auth"
import { nomeCategoria, useCategorias } from "@/lib/api/categorias"
import {
  MODOS_COM_PARTES,
  ROTULO_MODO,
  useCriarDivisao,
  useTransacoesCandidatas,
  type ModoDivisao,
} from "@/lib/api/divisoes"
import {
  descricaoExibida,
  valorEfetivoCentavos,
  type Transacao,
} from "@/lib/api/transacoes"
import { diaCivilSP, formatBRL, formatDate, hojeISO } from "@/lib/format"
import {
  partesPayload,
  partesValidas,
  proporcional,
  type Partes,
} from "@/lib/divisao-partes"
import { cn } from "@/lib/utils"

const PASSOS: Record<number, string> = {
  1: "Sobre a despesa",
  2: "Quem pagou?",
  3: "Como dividir?",
  4: "Com quem?",
  5: "Qual transação?",
  6: "Revisar divisão",
}

/** Onde a despesa paga por você aparece no banco: uma transação, depois, ou fora do banco. */
type Vinculo = "depois" | "fora" | number

function estadoInicial(transacao?: Transacao) {
  return {
    passo: 1,
    descricao: transacao ? (descricaoExibida(transacao) ?? "") : "",
    categoriaId: transacao?.categoria_efetiva_id ?? null,
    valor: transacao ? Math.abs(valorEfetivoCentavos(transacao)) : 0,
    data: transacao ? diaCivilSP(transacao.date) : hojeISO(),
    pagoPorMim: true,
    pagador: null as PessoaSelecionada | null,
    modo: "igualmente" as ModoDivisao,
    participantes: [] as PessoaSelecionada[],
    devedor: null as PessoaSelecionada | null,
    partes: {} as Partes,
    vinculo: "depois" as Vinculo,
    // Transação escolhida com valor diferente do total: reajustar a divisão a ela?
    reajustar: false,
  }
}

/** Wizard de criação de uma divisão de despesa (§4.11) — primeiro fluxo multi-passo do app (os
 *  demais dialogs de orçamento/objetivo são formulário único). Um só `Dialog`, corpo e rodapé
 *  trocam por passo; nada é salvo até "Salvar divisão" no passo final. */
export function NovaDivisaoWizard({
  trigger,
  initialOpen = false,
  onClose,
  transacao,
}: {
  trigger: React.ReactNode
  initialOpen?: boolean
  onClose?: () => void
  /** Divide esta saída: pré-preenche a despesa e fixa "eu paguei" + o vínculo. */
  transacao?: Transacao
}) {
  const [aberto, setAberto] = useState(initialOpen)
  const [form, setForm] = useState(() => estadoInicial(transacao))
  const me = useMe()
  const categorias = useCategorias()
  const criar = useCriarDivisao()

  function fechar(v: boolean) {
    setAberto(v)
    if (!v) {
      setForm(estadoInicial(transacao))
      onClose?.()
    }
  }

  const meuId = me.data?.id ?? null
  const pagoPorId = form.pagoPorMim ? meuId : (form.pagador?.id ?? null)
  const pagoPorNome = form.pagoPorMim ? "Você" : (form.pagador?.nome ?? null)
  // A busca de pessoas (`/api/usuarios/buscar`) sempre exclui quem está logado — não tem como
  // "encontrar a si mesmo" nela. Por isso o próprio objeto (nome/avatar já conhecidos) é montado
  // aqui para pré-selecionar você como participante/devedor por padrão (§4.11).
  const pessoaEu: PessoaSelecionada | null =
    meuId !== null
      ? {
          id: meuId,
          nome: me.data?.nome ?? "Você",
          avatar: me.data?.avatar ?? null,
        }
      : null

  const comPartes = MODOS_COM_PARTES.includes(form.modo)
  const modoPartes = form.modo === "valor" ? "valor" : "porcentagem"
  // Porcentagem/valor: quem pagou também tem fatia (pode ser 0), seguido dos escolhidos.
  const pagadorPessoa = form.pagoPorMim ? pessoaEu : form.pagador
  const pessoasPartes = [
    ...(pagadorPessoa ? [pagadorPessoa] : []),
    ...form.participantes.filter((p) => p.id !== pagoPorId),
  ]

  // Passos ativos: com transação, "quem pagou" é você (pula o 2); o passo da transação só existe
  // quando você pagou e ela ainda não foi escolhida.
  const passos = [
    1,
    ...(transacao ? [] : [2]),
    3,
    4,
    // Conta "somente divisão" não tem transações de banco para escolher.
    ...(form.pagoPorMim && !transacao && me.data?.tipo === "completo"
      ? [5]
      : []),
    6,
  ]
  const indice = passos.indexOf(form.passo)
  const ultimo = indice === passos.length - 1

  function podeAvancar(): boolean {
    if (form.passo === 1)
      return form.descricao.trim().length > 0 && form.valor > 0 && !!form.data
    if (form.passo === 2) return form.pagoPorMim || form.pagador !== null
    if (form.passo === 4) {
      if (comPartes)
        return partesValidas(
          modoPartes,
          form.valor,
          pagoPorId,
          pessoasPartes,
          form.partes
        )
      return form.modo === "igualmente"
        ? form.participantes.some((p) => p.id !== pagoPorId)
        : form.devedor !== null
    }
    return true
  }

  function salvar() {
    if (!pagoPorId) return
    const participantes =
      form.modo === "integral"
        ? form.devedor
          ? [form.devedor.id]
          : []
        : comPartes
          ? []
          : form.participantes.map((p) => p.id)
    const transacaoId =
      transacao?.id ??
      (form.pagoPorMim && typeof form.vinculo === "number"
        ? form.vinculo
        : null)
    criar.mutate(
      {
        descricao: form.descricao || null,
        categoria_id: form.categoriaId,
        valor_total_centavos: form.valor,
        pago_por_usuario_id: pagoPorId,
        modo_divisao: form.modo,
        participantes,
        partes: comPartes ? partesPayload(pessoasPartes, form.partes) : null,
        // Meio-dia em Brasília: o dia civil escolhido não "vira" por fuso.
        data: `${form.data}T12:00:00-03:00`,
        transacao_id: transacaoId,
        sem_transacao: !transacao && form.pagoPorMim && form.vinculo === "fora",
        reajustar:
          (!!transacao || typeof form.vinculo === "number") && form.reajustar,
      },
      {
        onSuccess: () => {
          toast.success("Divisão criada.")
          fechar(false)
        },
        onError: (err) => toast.error(err.message),
      }
    )
  }

  const categoriaNome = form.categoriaId
    ? (() => {
        const c = (categorias.data ?? []).find(
          (c) => c.pluggy_id === form.categoriaId
        )
        return c ? nomeCategoria(c) : form.categoriaId
      })()
    : "Sem categoria"

  return (
    <Dialog open={aberto} onOpenChange={fechar}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nova divisão de conta</DialogTitle>
          <p className="text-xs text-muted-foreground">
            {indice + 1}. {PASSOS[form.passo]}
          </p>
        </DialogHeader>

        {form.passo === 1 ? (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="descricao">Descrição</Label>
              <Input
                id="descricao"
                placeholder="Ex.: Jantar no sábado"
                value={form.descricao}
                onChange={(e) =>
                  setForm({ ...form, descricao: e.target.value })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label>Categoria</Label>
              <CategoriaSelect
                value={form.categoriaId}
                onChange={(v) => setForm({ ...form, categoriaId: v })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="valor">Valor total</Label>
                <CurrencyInput
                  id="valor"
                  value={form.valor}
                  onChange={(c) => setForm({ ...form, valor: c })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="data">Data</Label>
                <Input
                  id="data"
                  type="date"
                  value={form.data}
                  disabled={!!transacao}
                  onChange={(e) => setForm({ ...form, data: e.target.value })}
                />
              </div>
            </div>
            {transacao ? (
              <p className="text-xs text-muted-foreground">
                Vinculada à transação de {formatDate(transacao.date)}. No
                orçamento conta só a sua parte.
              </p>
            ) : null}
          </div>
        ) : null}

        {form.passo === 2 ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <OpcaoCard
                icon={User}
                titulo="Eu paguei"
                descricao="A despesa foi paga por você"
                selecionado={form.pagoPorMim}
                onClick={() =>
                  setForm({
                    ...form,
                    pagoPorMim: true,
                    // Pagador entra automaticamente na divisão (backend, "igualmente") — não
                    // precisa (nem faz sentido) aparecer também como participante selecionável,
                    // nem ser o devedor (não dá pra dever a si mesmo, modo integral).
                    participantes: form.participantes.filter(
                      (p) => p.id !== meuId
                    ),
                    devedor: form.devedor?.id === meuId ? null : form.devedor,
                  })
                }
              />
              <OpcaoCard
                icon={Users}
                titulo="Outra pessoa"
                descricao="A despesa foi paga por outra pessoa"
                selecionado={!form.pagoPorMim}
                onClick={() =>
                  setForm({
                    ...form,
                    pagoPorMim: false,
                    // Quando outra pessoa paga, você não entra na divisão sozinho — precisa
                    // estar pré-selecionada em "com quem" (removível), senão fica de fora do
                    // rateio por padrão. Idem para "quem deve" no modo integral, sem sobrescrever
                    // uma escolha manual já feita.
                    participantes:
                      pessoaEu &&
                      !form.participantes.some((p) => p.id === meuId)
                        ? [...form.participantes, pessoaEu]
                        : form.participantes,
                    devedor: form.devedor === null ? pessoaEu : form.devedor,
                  })
                }
              />
            </div>
            {!form.pagoPorMim ? (
              <div className="space-y-1.5">
                <Label>Quem pagou</Label>
                <PessoaSelect
                  value={form.pagador}
                  onChange={(p) => setForm({ ...form, pagador: p })}
                />
              </div>
            ) : null}
          </div>
        ) : null}

        {form.passo === 3 ? (
          <div className="grid grid-cols-2 gap-2">
            <OpcaoCard
              icon={Divide}
              titulo="Dividir igualmente"
              descricao="Todos pagam partes iguais"
              selecionado={form.modo === "igualmente"}
              onClick={() => setForm({ ...form, modo: "igualmente" })}
            />
            <OpcaoCard
              icon={Percent}
              titulo="Por porcentagem"
              descricao="Cada um paga uma % (soma 100%)"
              selecionado={form.modo === "porcentagem"}
              onClick={() =>
                setForm({ ...form, modo: "porcentagem", partes: {} })
              }
            />
            <OpcaoCard
              icon={Coins}
              titulo="Por valor"
              descricao="Cada um paga um valor (soma o total)"
              selecionado={form.modo === "valor"}
              onClick={() => setForm({ ...form, modo: "valor", partes: {} })}
            />
            <OpcaoCard
              icon={Banknote}
              titulo={form.pagoPorMim ? "Eu recebo tudo" : "Ele recebe tudo"}
              descricao="Uma pessoa deve o valor total, sem dividir"
              selecionado={form.modo === "integral"}
              onClick={() => setForm({ ...form, modo: "integral" })}
            />
          </div>
        ) : null}

        {form.passo === 4 ? (
          <div className="space-y-1.5">
            <Label>
              {form.modo === "integral"
                ? "Quem deve o valor"
                : "Selecionar pessoas"}
            </Label>
            {form.modo !== "integral" ? (
              <>
                <PessoaMultiPicker
                  value={form.participantes}
                  onChange={(p) => setForm({ ...form, participantes: p })}
                  excluir={pagoPorId ? [pagoPorId] : []}
                  eu={pessoaEu}
                />
                {comPartes ? (
                  <div className="space-y-1.5 pt-2">
                    <Label>
                      {form.modo === "porcentagem"
                        ? "Porcentagem de cada um"
                        : "Valor de cada um"}
                    </Label>
                    <PartesEditor
                      modo={modoPartes}
                      total={form.valor}
                      pessoas={pessoasPartes}
                      partes={form.partes}
                      onChange={(partes) => setForm({ ...form, partes })}
                    />
                  </div>
                ) : null}
              </>
            ) : (
              <PessoaSelect
                value={form.devedor}
                onChange={(p) => setForm({ ...form, devedor: p })}
                excluir={pagoPorId ? [pagoPorId] : []}
              />
            )}
          </div>
        ) : null}

        {form.passo === 5 ? (
          <PassoTransacao
            valor={form.valor}
            data={form.data}
            vinculo={form.vinculo}
            onChange={(v) => setForm({ ...form, vinculo: v })}
            outros={outrosPrevistos(form, pagoPorId, pessoasPartes)}
            reajustar={form.reajustar}
            onReajustar={(r) => setForm({ ...form, reajustar: r })}
          />
        ) : null}

        {form.passo === 6 ? (
          <div className="space-y-3 rounded-lg border p-3 text-sm">
            <LinhaResumo rotulo="Descrição" valor={form.descricao || "—"} />
            <LinhaResumo rotulo="Categoria" valor={categoriaNome} />
            <LinhaResumo
              rotulo="Valor total"
              valor={<Valor centavos={form.valor} neutro />}
            />
            <LinhaResumo rotulo="Pago por" valor={pagoPorNome ?? "—"} />
            <LinhaResumo rotulo="Divisão" valor={ROTULO_MODO[form.modo]} />
            <LinhaResumo
              rotulo="Participantes"
              valor={
                comPartes
                  ? pessoasPartes
                      .filter((p) => (form.partes[p.id] ?? 0) > 0)
                      .map(
                        (p) =>
                          `${p.nome} ${
                            form.modo === "valor"
                              ? formatBRL(form.partes[p.id])
                              : `${((form.partes[p.id] ?? 0) / 100).toLocaleString("pt-BR")}%`
                          }`
                      )
                      .join(", ")
                  : form.modo === "igualmente"
                    ? form.participantes.map((p) => p.nome).join(", ") ||
                      "Só você"
                    : (form.devedor?.nome ?? "—")
              }
            />
            {form.pagoPorMim ? (
              <LinhaResumo
                rotulo="Transação"
                valor={
                  transacao || typeof form.vinculo === "number"
                    ? form.reajustar
                      ? "Vinculada (divisão reajustada ao valor dela)"
                      : "Vinculada"
                    : form.vinculo === "fora"
                      ? "Paguei fora do banco"
                      : "Escolher depois"
                }
              />
            ) : null}
          </div>
        ) : null}

        {/* Começou por uma transação e o total foi mudado no passo 1: mesma escolha do passo 5. */}
        {form.passo === 6 &&
        transacao &&
        form.valor !== Math.abs(valorEfetivoCentavos(transacao)) ? (
          <EscolhaReajuste
            totalDivisao={form.valor}
            valorTransacao={Math.abs(valorEfetivoCentavos(transacao))}
            outros={outrosPrevistos(form, pagoPorId, pessoasPartes)}
            reajustar={form.reajustar}
            onChange={(r) => setForm({ ...form, reajustar: r })}
          />
        ) : null}

        <DialogFooter className="justify-between sm:justify-between">
          {indice > 0 ? (
            <Button
              variant="outline"
              onClick={() => setForm({ ...form, passo: passos[indice - 1] })}
            >
              Voltar
            </Button>
          ) : (
            <DialogClose asChild>
              <Button variant="ghost">Cancelar</Button>
            </DialogClose>
          )}
          {!ultimo ? (
            <Button
              disabled={!podeAvancar()}
              onClick={() => setForm({ ...form, passo: passos[indice + 1] })}
            >
              Continuar
            </Button>
          ) : (
            <Button onClick={salvar} disabled={criar.isPending}>
              Salvar divisão
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Passo "Qual transação?" (RF03): saídas candidatas (mesmo valor primeiro, ±7 dias), ou deixar
 *  para depois (fica pendente de revisão), ou "paguei fora do banco". */
function PassoTransacao({
  valor,
  data,
  vinculo,
  onChange,
  outros,
  reajustar,
  onReajustar,
}: {
  valor: number
  data: string
  vinculo: Vinculo
  onChange: (v: Vinculo) => void
  outros: number
  reajustar: boolean
  onReajustar: (r: boolean) => void
}) {
  const candidatas = useTransacoesCandidatas(valor, `${data}T12:00:00-03:00`)
  const itens = candidatas.data ?? []
  const escolhida = itens.find((t) => t.id === vinculo)
  const valorEscolhida = escolhida
    ? Math.abs(valorEfetivoCentavos(escolhida))
    : null
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Indique a transação do banco para o orçamento contar só a sua parte.
      </p>
      {candidatas.isLoading ? (
        <p className="text-sm text-muted-foreground">Buscando transações…</p>
      ) : candidatas.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível buscar as transações.{" "}
          <button
            type="button"
            className="underline underline-offset-4"
            onClick={() => candidatas.refetch()}
          >
            Tentar de novo
          </button>
        </p>
      ) : itens.length > 0 ? (
        <ul
          className="max-h-56 divide-y overflow-y-auto rounded-lg border"
          aria-label="Transações candidatas"
        >
          {itens.map((t) => {
            const selecionada = vinculo === t.id
            return (
              <li key={t.id}>
                <button
                  type="button"
                  aria-pressed={selecionada}
                  onClick={() => onChange(t.id)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-muted/40",
                    selecionada && "bg-primary/10"
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">
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
            )
          })}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          Nenhuma saída sem divisão perto dessa data.
        </p>
      )}
      {valorEscolhida !== null && valorEscolhida !== valor ? (
        <EscolhaReajuste
          totalDivisao={valor}
          valorTransacao={valorEscolhida}
          outros={outros}
          reajustar={reajustar}
          onChange={onReajustar}
        />
      ) : null}
      <div className="grid grid-cols-2 gap-2">
        <OpcaoCard
          icon={CalendarClock}
          titulo="Escolher depois"
          descricao="Fica pendente de revisão"
          selecionado={vinculo === "depois"}
          onClick={() => onChange("depois")}
        />
        <OpcaoCard
          icon={Landmark}
          titulo="Fora do banco"
          descricao="Dinheiro ou conta não conectada"
          selecionado={vinculo === "fora"}
          onClick={() => onChange("fora")}
        />
      </div>
    </div>
  )
}

/** Quanto os outros vão dever, para a prévia do "manter a divisão". Igualmente é aproximado (o
 *  backend dá o centavo do resto aos primeiros ids); porcentagem usa o mesmo rateio do backend. */
function outrosPrevistos(
  form: ReturnType<typeof estadoInicial>,
  pagoPorId: number | null,
  pessoasPartes: PessoaSelecionada[]
) {
  if (form.modo === "integral") return form.valor
  if (form.modo === "igualmente") {
    const n = new Set([...form.participantes.map((p) => p.id), pagoPorId]).size
    return form.valor - Math.floor(form.valor / n)
  }
  if (form.modo === "valor")
    return pessoasPartes
      .filter((p) => p.id !== pagoPorId)
      .reduce((s, p) => s + (form.partes[p.id] ?? 0), 0)
  const fatias = proporcional(
    form.valor,
    pessoasPartes.map((p) => [p.id, form.partes[p.id] ?? 0])
  )
  return form.valor - (pagoPorId !== null ? (fatias[pagoPorId] ?? 0) : 0)
}

function LinhaResumo({
  rotulo,
  valor,
}: {
  rotulo: string
  valor: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{rotulo}</span>
      <span className="text-right font-medium">{valor}</span>
    </div>
  )
}
