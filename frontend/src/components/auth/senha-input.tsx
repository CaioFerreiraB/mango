import { Eye, EyeOff, Lock } from "lucide-react"
import { useState } from "react"

import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"

/** Campo de senha das telas públicas: cadeado + alternar visibilidade. As props vão direto pro
 *  input — no React 19 `ref` é prop comum, então `{...register("senha")}` funciona sem forwardRef. */
export function SenhaInput({
  className,
  ...props
}: React.ComponentProps<typeof InputGroupInput>) {
  const [visivel, setVisivel] = useState(false)

  return (
    <InputGroup className={className}>
      <InputGroupAddon>
        <Lock aria-hidden />
      </InputGroupAddon>
      <InputGroupInput {...props} type={visivel ? "text" : "password"} />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          size="icon-xs"
          aria-label={visivel ? "Ocultar senha" : "Mostrar senha"}
          aria-pressed={visivel}
          onClick={() => setVisivel((v) => !v)}
        >
          {visivel ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  )
}
