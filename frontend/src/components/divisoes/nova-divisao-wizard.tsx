import { Banknote, Divide, User, Users } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { CurrencyInput } from "@/components/common/currency-input"
import { Valor } from "@/components/common/valor"
import { OpcaoCard } from "@/components/divisoes/opcao-card"
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
import { useCriarDivisao, type ModoDivisao } from "@/lib/api/divisoes"

const PASSOS = [
  "Sobre a despesa",
  "Quem pagou?",
  "Como dividir?",
  "Com quem?",
  "Revisar divisão",
] as const

function estadoInicial() {
  return {
    passo: 1,
    descricao: "",
    categoriaId: null as string | null,
    valor: 0,
    pagoPorMim: true,
    pagador: null as PessoaSelecionada | null,
    modo: "igualmente" as ModoDivisao,
    participantes: [] as PessoaSelecionada[],
    devedor: null as PessoaSelecionada | null,
  }
}

/** Wizard de criação de uma divisão de despesa (§4.11) — primeiro fluxo multi-passo do app (os
 *  demais dialogs de orçamento/objetivo são formulário único). Um só `Dialog`, corpo e rodapé
 *  trocam por passo; nada é salvo até "Salvar divisão" no passo final. */
export function NovaDivisaoWizard({ trigger }: { trigger: React.ReactNode }) {
  const [aberto, setAberto] = useState(false)
  const [form, setForm] = useState(estadoInicial())
  const me = useMe()
  const categorias = useCategorias()
  const criar = useCriarDivisao()

  function fechar(v: boolean) {
    setAberto(v)
    if (!v) setForm(estadoInicial())
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

  function podeAvancar(): boolean {
    if (form.passo === 1)
      return form.descricao.trim().length > 0 && form.valor > 0
    if (form.passo === 2) return form.pagoPorMim || form.pagador !== null
    if (form.passo === 4)
      return form.modo === "igualmente" || form.devedor !== null
    return true
  }

  function salvar() {
    if (!pagoPorId) return
    const participantes =
      form.modo === "integral"
        ? form.devedor
          ? [form.devedor.id]
          : []
        : form.participantes.map((p) => p.id)
    criar.mutate(
      {
        descricao: form.descricao || null,
        categoria_id: form.categoriaId,
        valor_total_centavos: form.valor,
        pago_por_usuario_id: pagoPorId,
        modo_divisao: form.modo,
        participantes,
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
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nova divisão de conta</DialogTitle>
          <p className="text-xs text-muted-foreground">
            {form.passo}. {PASSOS[form.passo - 1]}
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
            <div className="space-y-1.5">
              <Label htmlFor="valor">Valor total</Label>
              <CurrencyInput
                id="valor"
                value={form.valor}
                onChange={(c) => setForm({ ...form, valor: c })}
              />
            </div>
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
              {form.modo === "igualmente"
                ? "Selecionar pessoas"
                : "Quem deve o valor"}
            </Label>
            {form.modo === "igualmente" ? (
              <PessoaMultiPicker
                value={form.participantes}
                onChange={(p) => setForm({ ...form, participantes: p })}
                excluir={pagoPorId ? [pagoPorId] : []}
                eu={pessoaEu}
              />
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
          <div className="space-y-3 rounded-lg border p-3 text-sm">
            <LinhaResumo rotulo="Descrição" valor={form.descricao || "—"} />
            <LinhaResumo rotulo="Categoria" valor={categoriaNome} />
            <LinhaResumo
              rotulo="Valor total"
              valor={<Valor centavos={form.valor} neutro />}
            />
            <LinhaResumo rotulo="Pago por" valor={pagoPorNome ?? "—"} />
            <LinhaResumo
              rotulo="Divisão"
              valor={
                form.modo === "igualmente"
                  ? "Dividir igualmente"
                  : "Valor integral"
              }
            />
            <LinhaResumo
              rotulo="Participantes"
              valor={
                form.modo === "igualmente"
                  ? form.participantes.map((p) => p.nome).join(", ") ||
                    "Só você"
                  : (form.devedor?.nome ?? "—")
              }
            />
          </div>
        ) : null}

        <DialogFooter className="justify-between sm:justify-between">
          {form.passo > 1 ? (
            <Button
              variant="outline"
              onClick={() => setForm({ ...form, passo: form.passo - 1 })}
            >
              Voltar
            </Button>
          ) : (
            <DialogClose asChild>
              <Button variant="ghost">Cancelar</Button>
            </DialogClose>
          )}
          {form.passo < 5 ? (
            <Button
              disabled={!podeAvancar()}
              onClick={() => setForm({ ...form, passo: form.passo + 1 })}
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
