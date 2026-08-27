import { Repeat, Wand2 } from "lucide-react"
import { Link } from "react-router"
import { toast } from "sonner"

import { RegraDialog } from "@/components/configuracoes/regras-categorizacao-card"
import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { useAssinaturas } from "@/lib/api/assinaturas"
import { useAtualizarTransacao, type Transacao } from "@/lib/api/transacoes"

/** Nome que as regras comparam — o mesmo par que o backend usa (`merchant_nome`, `description`). */
function nomeParaRegra(t: Transacao): string {
  return (t.merchant_nome ?? t.description ?? "").trim()
}

/** Categoria da transação: escolha, proveniência e o atalho para virar regra (§4.5).
 *
 * A precedência é resolvida no servidor (`categoria_efetiva_id`/`categoria_origem`) — replicá-la
 * aqui daria divergência silenciosa entre o que a lista soma e o que o drawer mostra.
 */
export function CampoCategoria({ transacao: t }: { transacao: Transacao }) {
  const atualizar = useAtualizarTransacao()
  const assinaturas = useAssinaturas()
  const daAssinatura = t.categoria_origem === "assinatura"
  const assinatura = assinaturas.data?.find((a) => a.id === t.assinatura_id)
  const parcelas = t.total_installments ?? 0
  const nome = nomeParaRegra(t)

  return (
    <div className="space-y-1.5">
      <Label>Categoria</Label>
      <CategoriaSelect
        className="w-full"
        value={t.categoria_efetiva_id ?? null}
        disabled={daAssinatura}
        onChange={(v) =>
          v &&
          atualizar.mutate(
            {
              id: t.id,
              patch: {
                categoria_override_id: v,
                categoria_ajustada_usuario: true,
              },
            },
            {
              onSuccess: () =>
                parcelas > 1
                  ? toast.success(
                      "Categoria aplicada a todas as parcelas desta compra."
                    )
                  : undefined,
              onError: (err) => toast.error(err.message),
            }
          )
        }
      />

      <Procedencia transacao={t} assinaturaNome={assinatura?.nome} />

      {daAssinatura ? null : parcelas > 1 ? (
        <p className="text-xs text-muted-foreground">
          Compra em {parcelas}x — mudar aqui vale para todas as parcelas já
          lançadas.
        </p>
      ) : null}

      {!daAssinatura && nome ? (
        <RegraDialog
          textoInicial={nome}
          categoriaInicial={t.categoria_efetiva_id ?? null}
          gatilho={
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground"
            >
              <Wand2 className="size-3.5" aria-hidden />
              Sempre categorizar “{nome}” assim
            </Button>
          }
        />
      ) : null}
    </div>
  )
}

function Procedencia({
  transacao: t,
  assinaturaNome,
}: {
  transacao: Transacao
  assinaturaNome?: string
}) {
  const classe = "text-xs text-muted-foreground"

  switch (t.categoria_origem) {
    case "assinatura":
      return (
        <p className={`flex flex-wrap items-center gap-1 ${classe}`}>
          <Repeat className="size-3.5 shrink-0" aria-hidden />
          Vem da assinatura
          <Link
            to="/assinaturas"
            className="font-medium text-foreground underline underline-offset-2"
          >
            {assinaturaNome ?? "vinculada"}
          </Link>
          — altere por lá para valer em todas as cobranças.
        </p>
      )
    case "manual":
      return <p className={classe}>Categoria ajustada por você.</p>
    case "regra":
      return (
        <p className={classe}>
          Definida por uma{" "}
          <Link
            to="/configuracoes?aba=categorias"
            className="underline underline-offset-2"
          >
            regra automática
          </Link>
          .
        </p>
      )
    case "banco":
      return <p className={classe}>Sugestão do banco.</p>
    default:
      return (
        <p className={classe}>
          Sem categoria — o banco não sugeriu nenhuma, ou a que ele sugeriu está
          desativada.
        </p>
      )
  }
}
