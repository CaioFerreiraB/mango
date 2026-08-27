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
              // Quem sabe quantas irmãs foram alcançadas é o servidor (o agrupamento das parcelas
              // é heurístico e pode não achar nenhuma) — anunciar por `total_installments > 1`
              // prometia o que não tinha acontecido.
              onSuccess: (atualizada) =>
                atualizada.parcelas_atualizadas > 0
                  ? toast.success(
                      `Categoria aplicada também a ${atualizada.parcelas_atualizadas} outra(s) parcela(s) desta compra.`
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
          {/* Condicional de propósito: o agrupamento das parcelas é heurístico (o banco não manda
              id de compra) e pode não achar nenhuma irmã. Prometer "vale para todas" antes da
              ação era uma garantia que o sistema não tem como dar — quantas foram de fato sai no
              aviso depois, com o número que o servidor devolveu. */}
          Compra em {parcelas}x — as outras parcelas já lançadas que o sistema
          reconhecer como desta mesma compra acompanham a mudança.
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
