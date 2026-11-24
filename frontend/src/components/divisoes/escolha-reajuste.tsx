import { useId } from "react"

import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { formatBRL } from "@/lib/format"

/** Transação com valor diferente da divisão: manter a divisão (o orçamento conta a transação
 *  menos a parte dos outros) ou reajustá-la ao valor da transação, na mesma proporção. */
export function EscolhaReajuste({
  totalDivisao,
  valorTransacao,
  outros,
  podeReajustar = true,
  reajustar,
  onChange,
}: {
  totalDivisao: number
  valorTransacao: number
  /** Parte dos outros, quando já é conhecida (divisão existente). */
  outros: number | null
  podeReajustar?: boolean
  reajustar: boolean
  onChange: (reajustar: boolean) => void
}) {
  const id = useId()
  const manter =
    outros === null
      ? "No orçamento fica o valor da transação menos a parte dos outros. Quanto eles devem não muda."
      : `No orçamento fica ${formatBRL(valorTransacao)} − ${formatBRL(outros)} da parte dos outros = ${formatBRL(Math.max(valorTransacao - outros, 0))}. Quanto eles devem não muda.`
  return (
    <div className="space-y-2 rounded-lg border bg-muted/30 p-3 text-sm">
      <p className="font-medium">
        A transação de {formatBRL(valorTransacao)} tem valor diferente da
        divisão de {formatBRL(totalDivisao)}.
      </p>
      <RadioGroup
        value={reajustar ? "reajustar" : "manter"}
        onValueChange={(v) => onChange(v === "reajustar")}
        aria-label="O que fazer com a diferença"
      >
        <div className="flex items-start gap-2">
          <RadioGroupItem
            value="manter"
            id={`${id}-manter`}
            className="mt-0.5"
          />
          <Label htmlFor={`${id}-manter`} className="block font-normal">
            <span className="font-medium">
              Manter a divisão de {formatBRL(totalDivisao)}
            </span>
            <span className="block text-xs text-muted-foreground">
              {manter}
            </span>
          </Label>
        </div>
        <div className="flex items-start gap-2">
          <RadioGroupItem
            value="reajustar"
            id={`${id}-reajustar`}
            className="mt-0.5"
            disabled={!podeReajustar}
          />
          <Label htmlFor={`${id}-reajustar`} className="block font-normal">
            <span className="font-medium">
              Reajustar a divisão para {formatBRL(valorTransacao)}
            </span>
            <span className="block text-xs text-muted-foreground">
              {podeReajustar
                ? "As partes são recalculadas na mesma proporção."
                : "Só quem criou a divisão pode reajustá-la."}
            </span>
          </Label>
        </div>
      </RadioGroup>
    </div>
  )
}
