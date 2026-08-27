import { useState } from "react"
import { CreditCard } from "lucide-react"
import { Link, useSearchParams } from "react-router"

import { AvatarBanco } from "@/components/contas/avatar-banco"
import { EmptyState } from "@/components/common/empty-state"
import { Valor } from "@/components/common/valor"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useContas } from "@/lib/api/contas"
import { useFaturas } from "@/lib/api/faturas"
import { instituicaoEfetiva, useInstituicoes } from "@/lib/api/instituicoes"
import { formatDate, formatMesAno, mesISO, statusFatura } from "@/lib/format"

const TODAS = "__todas__"

/** Últimos 4 dígitos do número da conta/cartão (ou o número inteiro, se tiver ≤4). */
function ult4(numero?: string | null): string | null {
  if (!numero) return null
  const so = numero.replace(/\s/g, "")
  return so.length <= 4 ? so : so.slice(-4)
}

/** Nome do cartão + sufixo `****1234` menor e esmaecido (só quando há número). */
function NomeCartao({
  nome,
  numero,
}: {
  nome: string
  numero?: string | null
}) {
  const u = ult4(numero)
  return (
    <>
      {nome}
      {u ? (
        <span className="ml-1 text-xs font-normal text-muted-foreground">
          ****{u}
        </span>
      ) : null}
    </>
  )
}

export function FaturasPage() {
  const { data, isLoading, isError } = useFaturas()
  const contas = useContas()
  const instituicoes = useInstituicoes()

  const [params] = useSearchParams()
  const [mesKey, setMesKey] = useState<string | null>(null)
  const [instituicaoId, setInstituicaoId] = useState<number | null>(null)
  const [cartaoId, setCartaoId] = useState<number | null>(
    params.get("cartao_id") ? Number(params.get("cartao_id")) : null
  )

  // fatura.cartao_id === conta.id (do cartão). O título do card é o nome da própria conta
  // (marketing_name/nome); o filtro e o logo usam a instituição efetiva (manual, se vinculada).
  const contaPorId = new Map((contas.data ?? []).map((c) => [c.id, c]))
  const instPorId = new Map((instituicoes.data ?? []).map((i) => [i.id, i]))
  const banco = (cid: number) => {
    const c = contaPorId.get(cid)
    return c?.marketing_name ?? c?.nome ?? "Conta"
  }
  // Instituição efetiva da conta de um cartão + seu id (manual sobrepõe a original do sync).
  const instConta = (cid: number) => {
    const c = contaPorId.get(cid)
    return c ? instituicaoEfetiva(c, instPorId) : undefined
  }
  const instContaId = (cid: number) => {
    const c = contaPorId.get(cid)
    return c ? (c.instituicao_manual_id ?? c.instituicao_id) : null
  }

  const faturas = data ?? []

  // Opções derivadas só das faturas presentes (nada de dropdown vazio), agrupando pela
  // instituição efetiva e rotulando com o nome dela (fallback ao nome da conta).
  const inst = new Map<number, string>()
  for (const f of faturas) {
    const iid = instContaId(f.cartao_id)
    if (iid != null && !inst.has(iid)) {
      inst.set(iid, instConta(f.cartao_id)?.nome ?? banco(f.cartao_id))
    }
  }
  const opcoesInstituicao = [...inst]
    .map(([id, nome]) => ({ id, nome }))
    .sort((a, b) => a.nome.localeCompare(b.nome))

  const opcoesCartao = [...new Set(faturas.map((f) => f.cartao_id))]
    .map((id) => ({ id, nome: banco(id), numero: contaPorId.get(id)?.numero }))
    .sort(
      (a, b) =>
        a.nome.localeCompare(b.nome) ||
        (a.numero ?? "").localeCompare(b.numero ?? "")
    )

  // Meses presentes (competência do vencimento), rotulados "junho de 2026", mais recente primeiro.
  const opcoesMes = [
    ...new Map(
      faturas.map((f) => [mesISO(f.due_date), formatMesAno(f.due_date)])
    ),
  ]
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([key, label]) => ({ key, label }))

  const visiveis = faturas
    .filter((f) => {
      if (mesKey != null && mesISO(f.due_date) !== mesKey) return false
      if (cartaoId != null && f.cartao_id !== cartaoId) return false
      if (instituicaoId != null && instContaId(f.cartao_id) !== instituicaoId)
        return false
      return true
    })
    .slice()
    .sort((a, b) => (a.due_date < b.due_date ? 1 : -1))

  // Quebra por mês: visiveis já vem ordenada desc, então o mesmo mês é contíguo.
  const grupos: { key: string; label: string; itens: typeof visiveis }[] = []
  for (const f of visiveis) {
    const key = mesISO(f.due_date)
    const ultimo = grupos[grupos.length - 1]
    if (ultimo?.key === key) ultimo.itens.push(f)
    else grupos.push({ key, label: formatMesAno(f.due_date), itens: [f] })
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Faturas</h1>

      {isError ? (
        <EmptyState title="Não foi possível carregar as faturas" />
      ) : isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : faturas.length === 0 ? (
        <EmptyState
          icon={CreditCard}
          title="Nenhuma fatura ainda"
          description="Conecte um cartão de crédito pelo Open Finance para ver as faturas por competência."
        />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Select
              value={mesKey ?? TODAS}
              onValueChange={(v) => setMesKey(v === TODAS ? null : v)}
            >
              <SelectTrigger size="sm" className="w-full">
                <SelectValue placeholder="Mês" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={TODAS}>Todos os meses</SelectItem>
                {opcoesMes.map((o) => (
                  <SelectItem key={o.key} value={o.key} className="capitalize">
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={instituicaoId === null ? TODAS : String(instituicaoId)}
              onValueChange={(v) =>
                setInstituicaoId(v === TODAS ? null : Number(v))
              }
            >
              <SelectTrigger size="sm" className="w-full">
                <SelectValue placeholder="Instituição" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={TODAS}>Todas as instituições</SelectItem>
                {opcoesInstituicao.map((o) => (
                  <SelectItem key={o.id} value={String(o.id)}>
                    {o.nome}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={cartaoId === null ? TODAS : String(cartaoId)}
              onValueChange={(v) => setCartaoId(v === TODAS ? null : Number(v))}
            >
              <SelectTrigger size="sm" className="w-full">
                <SelectValue placeholder="Cartão" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={TODAS}>Todos os cartões</SelectItem>
                {opcoesCartao.map((o) => (
                  <SelectItem key={o.id} value={String(o.id)}>
                    <NomeCartao nome={o.nome} numero={o.numero} />
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {visiveis.length === 0 ? (
            <EmptyState title="Nenhuma fatura para os filtros selecionados" />
          ) : (
            <div className="flex flex-col gap-5">
              {grupos.map((g) => (
                <section key={g.key} className="flex flex-col gap-2">
                  <h2 className="text-sm font-semibold text-muted-foreground capitalize">
                    {g.label}
                  </h2>
                  <div className="flex flex-col gap-3">
                    {g.itens.map((f) => {
                      const st = statusFatura(f.due_date)
                      const nome = banco(f.cartao_id)
                      const numero = contaPorId.get(f.cartao_id)?.numero
                      return (
                        <Link key={f.id} to={`/faturas/${f.id}`}>
                          <Card className="transition-colors hover:border-primary/50">
                            <CardContent className="flex items-start gap-3 py-4">
                              <AvatarBanco
                                nome={nome}
                                logoUrl={instConta(f.cartao_id)?.logo_url}
                              />
                              {/* Texto + valor na mesma coluna: no mobile o valor quebra
                                  alinhado ao texto (não ao avatar); no desktop fica à direita. */}
                              <div className="flex min-w-0 flex-1 flex-wrap items-start justify-between gap-x-3 gap-y-2">
                                <div className="min-w-0">
                                  <p className="font-medium [overflow-wrap:anywhere] break-words">
                                    <NomeCartao nome={nome} numero={numero} />
                                  </p>
                                  <p className="mt-1 text-sm text-muted-foreground">
                                    Vencimento {formatDate(f.due_date)}
                                  </p>
                                  <div className="mt-1 flex flex-wrap items-center gap-2">
                                    <Badge
                                      variant={
                                        st.aberta ? "default" : "secondary"
                                      }
                                    >
                                      {st.rotulo}
                                    </Badge>
                                    {f.allows_installments ? (
                                      <Badge variant="outline">
                                        Permite parcelar
                                      </Badge>
                                    ) : null}
                                  </div>
                                </div>
                                <div className="text-left sm:text-right">
                                  <Valor
                                    centavos={f.total_amount_centavos}
                                    neutro
                                    className="text-base font-bold"
                                  />
                                  {f.minimum_payment_centavos ? (
                                    <p className="text-xs text-muted-foreground">
                                      Mínimo{" "}
                                      <Valor
                                        centavos={f.minimum_payment_centavos}
                                      />
                                    </p>
                                  ) : null}
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        </Link>
                      )
                    })}
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
