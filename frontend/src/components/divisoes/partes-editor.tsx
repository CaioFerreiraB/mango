import { CurrencyInput } from "@/components/common/currency-input"
import { PessoaAvatar } from "@/components/divisoes/pessoa-avatar"
import type { PessoaSelecionada } from "@/components/divisoes/pessoa-multi-picker"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  alvoPartes,
  CEM_POR_CENTO,
  comFatia,
  partesIguais,
  somaPartes,
  type ModoPartes,
  type Partes,
} from "@/lib/divisao-partes"
import { formatBRL } from "@/lib/format"
import { cn } from "@/lib/utils"

const pct = (bp: number) =>
  `${(bp / 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`

/** Uma linha por pessoa com a fatia dela (porcentagem ou R$) e o quanto falta/sobra para fechar
 *  100% ou o valor total. */
export function PartesEditor({
  modo,
  total,
  pessoas,
  partes,
  onChange,
}: {
  modo: ModoPartes
  total: number
  pessoas: PessoaSelecionada[]
  partes: Partes
  onChange: (p: Partes) => void
}) {
  const meta = alvoPartes(modo, total)
  const soma = somaPartes(pessoas, partes)
  const fmt = modo === "porcentagem" ? pct : formatBRL
  const diferenca = meta - soma
  const status =
    diferenca === 0
      ? `Soma ${fmt(meta)}`
      : diferenca > 0
        ? `Faltam ${fmt(diferenca)} de ${fmt(meta)}`
        : `Passou ${fmt(-diferenca)} de ${fmt(meta)}`

  return (
    <div className="space-y-2">
      <ul className="divide-y rounded-lg border">
        {pessoas.map((p) => {
          const v = partes[p.id] ?? 0
          const set = (n: number) =>
            onChange(comFatia(pessoas, partes, p.id, n, meta))
          return (
            <li key={p.id} className="flex items-center gap-3 p-2.5">
              <PessoaAvatar
                nome={p.nome}
                avatar={p.avatar}
                className="size-7"
              />
              <span className="min-w-0 flex-1 truncate text-sm">{p.nome}</span>
              {modo === "valor" ? (
                <CurrencyInput
                  value={v}
                  onChange={set}
                  aria-label={`Valor de ${p.nome}`}
                  className="w-32 text-right"
                />
              ) : (
                <span className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {formatBRL(Math.round((total * v) / CEM_POR_CENTO))}
                  </span>
                  <span className="relative">
                    <Input
                      type="number"
                      inputMode="decimal"
                      min={0}
                      max={100}
                      step={0.01}
                      value={v ? v / 100 : ""}
                      placeholder="0"
                      onChange={(e) =>
                        set(
                          Math.min(
                            CEM_POR_CENTO,
                            Math.max(
                              0,
                              Math.round(Number(e.target.value) * 100) || 0
                            )
                          )
                        )
                      }
                      aria-label={`Porcentagem de ${p.nome}`}
                      className="w-24 [appearance:textfield] pr-7 text-right [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                    />
                    <span
                      aria-hidden
                      className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-sm text-muted-foreground"
                    >
                      %
                    </span>
                  </span>
                </span>
              )}
            </li>
          )
        })}
      </ul>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span
          role="status"
          className={cn(
            "tabular-nums",
            diferenca === 0 ? "text-muted-foreground" : "text-negative"
          )}
        >
          {status}
        </span>
        <Button
          type="button"
          size="xs"
          variant="ghost"
          onClick={() => onChange(partesIguais(pessoas, meta))}
        >
          Dividir igualmente
        </Button>
      </div>
    </div>
  )
}
