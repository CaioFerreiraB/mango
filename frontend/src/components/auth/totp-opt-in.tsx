import { ShieldCheck } from "lucide-react"

import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"

/** Opt-in de 2FA do cadastro (§5.2, #15) — mesmo bloco no first-run setup e no aceite de convite. */
export function TotpOptIn({
  checked,
  onCheckedChange,
}: {
  checked: boolean
  onCheckedChange: (valor: boolean) => void
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-primary/20 bg-primary/5 p-3">
      <Checkbox
        id="ativar_totp"
        checked={checked}
        onCheckedChange={(v) => onCheckedChange(v === true)}
        className="mt-0.5"
      />
      <div className="flex flex-1 flex-col gap-1">
        <Label htmlFor="ativar_totp" className="font-normal">
          Ativar verificação em duas etapas (2FA)
        </Label>
        <p className="text-xs text-muted-foreground">
          Sem 2FA você não conseguirá recuperar a senha caso a esqueça.
        </p>
      </div>
      <span
        aria-hidden
        className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
      >
        <ShieldCheck className="size-5" />
      </span>
    </div>
  )
}
