import { Link } from "react-router"

import { AvatarBanco } from "@/components/contas/avatar-banco"
import { CartaoArt } from "@/components/contas/cartao-art"
import { SaldoSparkline } from "@/components/contas/saldo-sparkline"
import { Valor } from "@/components/common/valor"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import type { Conta, SaldoDiarioPonto } from "@/lib/api/contas"
import { instituicaoEfetiva, useInstituicoes } from "@/lib/api/instituicoes"
import { mascarar } from "@/lib/format"
import { cn } from "@/lib/utils"

export function ContaCard({
  conta,
  pontos,
}: {
  conta: Conta
  pontos?: SaldoDiarioPonto[]
}) {
  const isCartao = conta.type === "CREDIT"
  const nome = conta.marketing_name ?? conta.nome ?? "Conta"

  const instituicoes = useInstituicoes()
  const logoUrl = instituicaoEfetiva(
    conta,
    new Map((instituicoes.data ?? []).map((i) => [i.id, i]))
  )?.logo_url

  return (
    <Link to={`/contas/${conta.id}`} className="group">
      <Card
        className={cn(
          "relative h-full overflow-hidden transition-colors hover:border-primary/50",
          isCartao && "min-h-44 gap-3" // cartão: header + rodapé, arte sangrando no meio
        )}
      >
        {/* Cartão: arte posicionada relativa ao Card → começa na MESMA altura em todos, independente
            de o nome ter 1 ou 2 linhas. Tombada, mais à esquerda, sangrando pra baixo. */}
        {isCartao ? (
          <div className="pointer-events-none absolute top-20 right-8">
            <CartaoArt conta={conta} nome={nome} logoUrl={logoUrl} />
          </div>
        ) : null}

        <CardHeader className="flex-row items-start gap-3 pb-2">
          <AvatarBanco nome={nome} logoUrl={logoUrl} />
          <div className="min-w-0 flex-1">
            <p className="line-clamp-2 font-medium [overflow-wrap:anywhere] break-words">
              {nome}
            </p>
            <p className="text-xs text-muted-foreground">
              {mascarar(conta.numero)}
            </p>
          </div>
        </CardHeader>

        {isCartao ? null : (
          // Conta: saldo + sparkline dos últimos 30 dias sangrando até a borda (padrão do KpiCard).
          <CardContent className="flex items-end justify-between gap-2 pb-0">
            <div className="shrink-0 pb-6">
              <p className="text-lg">
                <Valor
                  centavos={conta.saldo_centavos}
                  neutro
                  className="font-bold text-primary"
                />
              </p>
            </div>
            {pontos && pontos.length >= 2 ? (
              <div className="-mr-6 min-w-0 flex-1 self-end">
                <SaldoSparkline pontos={pontos} />
              </div>
            ) : null}
          </CardContent>
        )}
      </Card>
    </Link>
  )
}
