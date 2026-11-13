import { Landmark } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  useAtivos,
  useCriarAtivo,
  useRenomearAtivo,
  useVincularAtivo,
  type CarteiraAtivoRF,
} from "@/lib/api/investimentos"
import { nomeAtivo } from "@/lib/investimento-taxonomia"

/** Dialogs do agrupamento de renda fixa em `ativo` (§4.9) — usados pela Carteira (aba Compras do
 *  drawer) e pela carteira legado. */

type AtivoRenomeavel = Pick<CarteiraAtivoRF, "ativo_id" | "nome">
export type ComprasParaMover = { ids: number[]; titulo: string }

export function RenomearAtivoDialog({
  ativo,
  onFechar,
}: {
  ativo: AtivoRenomeavel | null
  onFechar: () => void
}) {
  return (
    <Dialog open={ativo != null} onOpenChange={(a) => !a && onFechar()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Renomear ativo</DialogTitle>
          <DialogDescription>
            Um nome que agrupe as compras deste papel.
          </DialogDescription>
        </DialogHeader>
        {/* key remonta com estado fresco a cada ativo (evita setState em efeito) */}
        {ativo?.ativo_id != null ? (
          <RenomearForm
            key={ativo.ativo_id}
            ativo={ativo}
            onFechar={onFechar}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function RenomearForm({
  ativo,
  onFechar,
}: {
  ativo: AtivoRenomeavel
  onFechar: () => void
}) {
  const renomear = useRenomearAtivo()
  const [nome, setNome] = useState(ativo.nome ?? "")
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        const limpo = nome.trim()
        if (ativo.ativo_id != null && limpo)
          renomear.mutate(
            { id: ativo.ativo_id, nome: limpo },
            { onSuccess: onFechar }
          )
      }}
      className="flex gap-2"
    >
      <Input
        value={nome}
        onChange={(e) => setNome(e.target.value)}
        autoFocus
        maxLength={255}
        placeholder="Ex.: Caixinha Viagem"
      />
      <Button type="submit" disabled={!nome.trim() || renomear.isPending}>
        Salvar
      </Button>
    </form>
  )
}

/** Move uma ou várias compras (posições) p/ outro ativo — ou cria um novo, ex.: uma caixinha. */
export function MoverAtivoDialog({
  compras,
  onFechar,
  onMovido,
  mostrar,
}: {
  compras: ComprasParaMover | null
  onFechar: () => void
  onMovido?: () => void
  /** Filtra os destinos (ex.: só as caixinhas); sem ele, todos os ativos. */
  mostrar?: (ativoId: number) => boolean
}) {
  return (
    <Dialog open={compras != null} onOpenChange={(a) => !a && onFechar()}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 sm:max-w-sm">
        <DialogHeader className="shrink-0 pb-3">
          <DialogTitle>
            {compras && compras.ids.length > 1
              ? `Mover ${compras.ids.length} compras`
              : "Mover compra"}
          </DialogTitle>
          <DialogDescription className="truncate">
            {compras?.titulo ?? ""}
          </DialogDescription>
        </DialogHeader>
        {compras != null ? (
          <MoverConteudo
            key={compras.ids.join(",")}
            ids={compras.ids}
            mostrar={mostrar}
            onFechar={() => {
              onMovido?.()
              onFechar()
            }}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function MoverConteudo({
  ids,
  mostrar,
  onFechar,
}: {
  ids: number[]
  mostrar?: (ativoId: number) => boolean
  onFechar: () => void
}) {
  const ativos = useAtivos()
  const vincular = useVincularAtivo()
  const criar = useCriarAtivo()
  const [novo, setNovo] = useState("")

  const mover = (ativoId: number | null) =>
    vincular.mutate({ investimentoIds: ids, ativoId }, { onSuccess: onFechar })
  const criarEMover = () => {
    const nome = novo.trim()
    if (!nome) return
    criar.mutate(nome, { onSuccess: (a) => mover(a.id) })
  }
  const ocupado = criar.isPending || vincular.isPending
  return (
    <>
      <div className="min-h-0 space-y-1 overflow-y-auto">
        {(ativos.data ?? [])
          .filter((a) => !mostrar || mostrar(a.id))
          .map((a) => (
            <button
              key={a.id}
              type="button"
              disabled={ocupado}
              onClick={() => mover(a.id)}
              className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm transition-colors hover:bg-muted/60 disabled:opacity-50"
            >
              <Landmark
                className="size-4 shrink-0 text-muted-foreground"
                aria-hidden
              />
              <span className="truncate">{nomeAtivo(a.nome)}</span>
            </button>
          ))}
        <button
          type="button"
          disabled={ocupado}
          onClick={() => mover(null)}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-muted/60 disabled:opacity-50"
        >
          Deixar sem ativo (avulsa)
        </button>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          criarEMover()
        }}
        className="mt-3 flex shrink-0 gap-2 border-t pt-3"
      >
        <Input
          value={novo}
          onChange={(e) => setNovo(e.target.value)}
          maxLength={255}
          placeholder="Criar novo ativo…"
          aria-label="Nome do novo ativo"
        />
        <Button
          type="submit"
          variant="secondary"
          disabled={!novo.trim() || ocupado}
        >
          Criar
        </Button>
      </form>
    </>
  )
}
