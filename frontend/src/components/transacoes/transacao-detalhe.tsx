import { Check, Coins, CreditCard, Link2, Repeat, X } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { AssinaturaSelect } from "@/components/transacoes/assinatura-select"
import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import { StatusBadge } from "@/components/transacoes/status-badge"
import { Valor } from "@/components/common/valor"
import { Button } from "@/components/ui/button"
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { useIsMobile } from "@/hooks/use-mobile"
import { useAssinaturas } from "@/lib/api/assinaturas"
import { useContas } from "@/lib/api/contas"
import {
  useAtualizarTransacao,
  useProventosSugeridos,
  valorEfetivoCentavos,
  type Transacao,
} from "@/lib/api/transacoes"
import { sugerir } from "@/lib/assinatura-sugestao"
import { formatDateTime, formatMoeda } from "@/lib/format"

/** Sem isto o último campo do bottom sheet fica sob a barra de gestos. */
const SAFE_AREA_BOTTOM = "env(safe-area-inset-bottom)"

/** Painel de detalhe + edição estreita de uma transação (§4.5). Drawer flutuante à direita no
 *  desktop, bottom sheet no mobile. */
export function TransacaoDetalhe({
  transacao,
  onOpenChange,
  ocultarLinkFatura = false,
}: {
  transacao: Transacao | null
  onOpenChange: (aberto: boolean) => void
  /** Esconde o botão "Ir para a fatura" (ex.: já estamos na página da fatura). */
  ocultarLinkFatura?: boolean
}) {
  const atualizar = useAtualizarTransacao()
  const contas = useContas()
  // `direction` é comportamento do vaul (eixo da animação e do arraste), não dá para resolver por
  // CSS. Ao contrário da bottom nav, aqui o hook pode ser usado: o drawer nasce fechado, então o
  // `false` do primeiro paint não pisca nada.
  const isMobile = useIsMobile()
  const t = transacao
  const conta = contas.data?.find((c) => c.id === t?.conta_id)
  const contaNome = conta
    ? (conta.marketing_name ?? conta.nome ?? conta.pluggy_account_id)
    : null
  return (
    <Drawer
      direction={isMobile ? "bottom" : "right"}
      open={t !== null}
      onOpenChange={onOpenChange}
    >
      <DrawerContent
        className="gap-0 overflow-hidden shadow-xl data-[vaul-drawer-direction=bottom]:max-h-[85svh] data-[vaul-drawer-direction=right]:inset-y-2 data-[vaul-drawer-direction=right]:right-2 data-[vaul-drawer-direction=right]:rounded-l-2xl data-[vaul-drawer-direction=right]:rounded-r-2xl data-[vaul-drawer-direction=right]:border data-[vaul-drawer-direction=right]:sm:max-w-md"
        style={{ paddingBottom: isMobile ? SAFE_AREA_BOTTOM : undefined }}
      >
        {t ? (
          // A rolagem é deste wrapper, nunca do DrawerContent: o vaul põe nele um ::after de
          // `height: 200%` logo abaixo do painel (cobre o fundo enquanto se arrasta) e, com o
          // eixo vertical rolável, esse pseudo-elemento vira 2× de vazio rolável no bottom sheet.
          <div className="flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto">
            {/* O respiro generoso do valor é do painel lateral; no bottom sheet ele empurraria os
                campos para fora da dobra. */}
            <DrawerHeader className="items-center gap-1.5 pt-6 pb-8 text-center group-data-[vaul-drawer-direction=right]/drawer-content:pt-20 group-data-[vaul-drawer-direction=right]/drawer-content:pb-12 md:text-center">
              <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {t.type === "CREDIT" ? "Entrada" : "Saída"}
              </span>
              <DrawerTitle className="text-3xl font-semibold tracking-tight">
                <Valor
                  centavos={valorEfetivoCentavos(t)}
                  sinal
                  neutro
                  className="font-bold"
                />
              </DrawerTitle>
              <DrawerDescription className="sr-only">
                {`${t.description ?? "Transação"} · ${formatDateTime(t.date)}`}
              </DrawerDescription>
              <StatusBadge revisada={t.revisada} />
            </DrawerHeader>

            <div className="space-y-5 px-4 pb-6">
              {/* Detalhes — tabela sem bordas, rótulo à esquerda / valor à direita. */}
              <dl className="text-sm">
                {t.currency_code !== "BRL" ? (
                  <Linha rotulo="Valor original">
                    {formatMoeda(t.amount_centavos, t.currency_code)}
                  </Linha>
                ) : null}
                {t.description_raw ? (
                  <Linha rotulo="Descrição original">{t.description_raw}</Linha>
                ) : null}
                <Linha rotulo="Data">{formatDateTime(t.date)}</Linha>
                {contaNome ? <Linha rotulo="Conta">{contaNome}</Linha> : null}
                {t.merchant_nome ? (
                  <Linha rotulo="Estabelecimento">{t.merchant_nome}</Linha>
                ) : null}
                {t.installment_number && t.total_installments ? (
                  <Linha rotulo="Parcela">
                    {t.installment_number}/{t.total_installments}
                  </Linha>
                ) : null}
                {t.status === "PENDING" ? (
                  <Linha rotulo="Situação">Em processamento</Linha>
                ) : null}
              </dl>

              <div className="space-y-1.5">
                <Label>Categoria</Label>
                <CategoriaSelect
                  className="w-full"
                  value={
                    t.categoria_override_id ?? t.categoria_pluggy_id ?? null
                  }
                  onChange={(v) =>
                    v &&
                    atualizar.mutate({
                      id: t.id,
                      patch: {
                        categoria_override_id: v,
                        categoria_ajustada_usuario: true,
                      },
                    })
                  }
                />
                {t.categoria_ajustada_usuario ? (
                  <p className="text-xs text-muted-foreground">
                    Categoria ajustada por você.
                  </p>
                ) : null}
              </div>

              <div className="space-y-3 rounded-lg border p-3">
                <label className="flex items-center justify-between gap-2 text-sm">
                  Transação revisada
                  <Switch
                    checked={t.revisada}
                    onCheckedChange={(c) =>
                      atualizar.mutate({ id: t.id, patch: { revisada: c } })
                    }
                  />
                </label>
                <label className="flex items-center justify-between gap-2 text-sm">
                  É transferência interna
                  <Switch
                    checked={t.eh_transferencia}
                    onCheckedChange={(c) =>
                      atualizar.mutate({
                        id: t.id,
                        patch: { eh_transferencia: c },
                      })
                    }
                  />
                </label>
                <AssinaturaCampo key={t.id} transacao={t} />
                {t.type === "CREDIT" ? (
                  <ProventoCampo key={`prov-${t.id}`} transacao={t} />
                ) : null}
              </div>

              {t.contraparte_id ? (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Link2 className="size-4" aria-hidden />
                  Pareada como transferência entre suas contas.
                </p>
              ) : null}
            </div>

            {t.bill_id && !ocultarLinkFatura ? (
              <DrawerFooter>
                <Button asChild variant="outline">
                  <Link to={`/faturas/${t.bill_id}`}>
                    <CreditCard className="size-4" aria-hidden />
                    Ir para a fatura
                  </Link>
                </Button>
              </DrawerFooter>
            ) : null}
          </div>
        ) : null}
      </DrawerContent>
    </Drawer>
  )
}

/** Switch "é assinatura?" + combobox (§4.7). Ligar revela o seletor; escolher vincula (o backend
 *  aprende o nome como alias); desligar limpa o vínculo. `key={t.id}` reseta o estado por transação. */
function AssinaturaCampo({ transacao }: { transacao: Transacao }) {
  const atualizar = useAtualizarTransacao()
  const assinaturas = useAssinaturas()
  const [mostrar, setMostrar] = useState(transacao.assinatura_id != null)
  const vinculada = transacao.assinatura_id != null

  // Sugestão por semelhança de nome (§4.7): só para saída ainda sem vínculo e não rejeitada.
  const sugestao =
    !vinculada &&
    !transacao.nao_e_assinatura &&
    transacao.type === "DEBIT" &&
    !transacao.eh_transferencia
      ? sugerir(
          transacao.merchant_nome ?? transacao.description,
          assinaturas.data ?? []
        )
      : null

  return (
    <div className="space-y-2">
      <label className="flex items-center justify-between gap-2 text-sm">
        É uma assinatura
        <Switch
          checked={vinculada || mostrar}
          onCheckedChange={(c) => {
            setMostrar(c)
            if (!c && vinculada)
              atualizar.mutate({
                id: transacao.id,
                patch: { assinatura_id: null },
              })
          }}
        />
      </label>
      {sugestao && !mostrar ? (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md bg-muted/50 p-2 text-xs">
          <span className="flex items-center gap-1 text-muted-foreground">
            <Repeat className="size-3.5 shrink-0" aria-hidden />
            Parece a assinatura{" "}
            <span className="font-medium text-foreground">{sugestao.nome}</span>
          </span>
          <div className="flex gap-1">
            <Button
              size="xs"
              variant="secondary"
              disabled={atualizar.isPending}
              onClick={() =>
                atualizar.mutate(
                  { id: transacao.id, patch: { assinatura_id: sugestao.id } },
                  {
                    onSuccess: () =>
                      toast.success(`Vinculada a ${sugestao.nome}.`),
                    onError: (err) => toast.error(err.message),
                  }
                )
              }
            >
              <Check className="size-3.5" /> Confirmar
            </Button>
            <Button
              size="xs"
              variant="ghost"
              disabled={atualizar.isPending}
              onClick={() =>
                atualizar.mutate(
                  { id: transacao.id, patch: { nao_e_assinatura: true } },
                  {
                    onSuccess: () => toast.success("Ok, não é assinatura."),
                    onError: (err) => toast.error(err.message),
                  }
                )
              }
            >
              <X className="size-3.5" /> Rejeitar
            </Button>
          </div>
        </div>
      ) : null}
      {vinculada || mostrar ? (
        <AssinaturaSelect
          value={transacao.assinatura_id ?? null}
          onChange={(v) =>
            atualizar.mutate({ id: transacao.id, patch: { assinatura_id: v } })
          }
        />
      ) : null}
    </div>
  )
}

/** Vínculo com um provento de investimento (§4.9): só p/ entradas (CREDIT). Sugere por valor+data
 *  (como a assinatura) e permite desvincular. `key={prov-t.id}` reseta o estado por transação. */
function ProventoCampo({ transacao }: { transacao: Transacao }) {
  const atualizar = useAtualizarTransacao()
  const vinculado = transacao.investimento_transacao_id != null
  const sugestoes = useProventosSugeridos(transacao.id, !vinculado)
  const candidato = sugestoes.data?.[0]

  if (vinculado) {
    return (
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Coins className="size-4 shrink-0" aria-hidden />
          Provento de investimento
        </span>
        <Button
          size="xs"
          variant="ghost"
          disabled={atualizar.isPending}
          onClick={() =>
            atualizar.mutate(
              { id: transacao.id, patch: { investimento_transacao_id: null } },
              {
                onSuccess: () => toast.success("Vínculo removido."),
                onError: (err) => toast.error(err.message),
              }
            )
          }
        >
          Desvincular
        </Button>
      </div>
    )
  }
  if (!candidato) return null
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md bg-muted/50 p-2 text-xs">
      <span className="flex items-center gap-1 text-muted-foreground">
        <Coins className="size-3.5 shrink-0" aria-hidden />
        Parece um provento de investimento
      </span>
      <Button
        size="xs"
        variant="secondary"
        disabled={atualizar.isPending}
        onClick={() =>
          atualizar.mutate(
            {
              id: transacao.id,
              patch: { investimento_transacao_id: candidato.id },
            },
            {
              onSuccess: () => toast.success("Provento vinculado."),
              onError: (err) => toast.error(err.message),
            }
          )
        }
      >
        <Check className="size-3.5" /> Vincular
      </Button>
    </div>
  )
}

function Linha({
  rotulo,
  children,
}: {
  rotulo: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 first:pt-0">
      <dt className="shrink-0 text-muted-foreground">{rotulo}</dt>
      <dd className="min-w-0 text-right font-medium break-words">{children}</dd>
    </div>
  )
}
