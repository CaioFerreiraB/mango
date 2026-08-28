import { useRef, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ACCENT_PADRAO,
  ACCENTS,
  aplicarAccent,
  type Accent,
} from "@/lib/accent"
import { useAtualizarPerfil, usePerfil, type Perfil } from "@/lib/api/perfil"
import {
  AVATAR_PADRAO,
  AVATARES_DISPONIVEIS,
  ilustracao,
} from "@/lib/illustrations"
import { cn } from "@/lib/utils"

const NOMES_ACCENT: Record<Accent, string> = {
  violeta: "Violeta",
  manga: "Manga",
  verde: "Verde",
  azul: "Azul",
  rosa: "Rosa",
  teal: "Teal",
}

const AVATARES = [1, 2, 3, 4]

export function PreferenciasTab() {
  const perfil = usePerfil()
  if (perfil.isLoading || !perfil.data)
    return <Skeleton className="h-72 w-full" />
  return <PreferenciasForm key={perfil.data.id} perfil={perfil.data} />
}

function PreferenciasForm({ perfil }: { perfil: Perfil }) {
  const atualizar = useAtualizarPerfil()
  const accentAtual = (perfil.accent ?? ACCENT_PADRAO) as Accent
  const avatarAtual = perfil.avatar ?? AVATAR_PADRAO

  function escolherAccent(accent: Accent) {
    if (accent === accentAtual) return
    aplicarAccent(accent) // otimista: aplica já; reverte se o servidor recusar
    atualizar.mutate(
      { accent },
      {
        onError: (err) => {
          aplicarAccent(accentAtual)
          toast.error(err.message)
        },
      }
    )
  }

  function escolherAvatar(valor: string) {
    atualizar.mutate(
      { avatar: Number(valor) },
      { onError: (err) => toast.error(err.message) }
    )
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cor principal</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            role="radiogroup"
            aria-label="Cor principal"
            className="flex flex-wrap gap-4"
          >
            {(Object.keys(ACCENTS) as Accent[]).map((accent) => (
              <button
                key={accent}
                type="button"
                role="radio"
                aria-checked={accent === accentAtual}
                onClick={() => escolherAccent(accent)}
                className="flex flex-col items-center gap-1.5 rounded-lg p-1 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <span
                  aria-hidden
                  style={{ backgroundColor: ACCENTS[accent] }}
                  className={cn(
                    "size-8 rounded-full transition-shadow",
                    accent === accentAtual &&
                      "ring-2 ring-foreground ring-offset-2 ring-offset-background"
                  )}
                />
                <span
                  className={cn(
                    "text-xs",
                    accent === accentAtual
                      ? "font-medium text-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  {NOMES_ACCENT[accent]}
                </span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Avatar</CardTitle>
        </CardHeader>
        <CardContent>
          <RadioGroup
            value={String(avatarAtual)}
            onValueChange={escolherAvatar}
            className="flex flex-wrap gap-4"
          >
            {AVATARES.map((n) => {
              const disponivel = AVATARES_DISPONIVEIS.includes(n)
              return (
                <Label
                  key={n}
                  className={cn(
                    "flex w-28 flex-col items-center gap-2 rounded-xl border p-3",
                    disponivel
                      ? "cursor-pointer has-data-checked:border-primary has-data-checked:bg-primary/5"
                      : "opacity-50"
                  )}
                >
                  {disponivel ? (
                    <img
                      src={ilustracao(n, "default")}
                      alt={`Avatar ${n}`}
                      className="size-16 rounded-lg object-contain"
                    />
                  ) : (
                    <span className="flex size-16 items-center justify-center rounded-lg bg-muted text-xs text-muted-foreground">
                      em breve
                    </span>
                  )}
                  <span className="flex items-center gap-2 text-sm">
                    <RadioGroupItem value={String(n)} disabled={!disponivel} />
                    Avatar {n}
                  </span>
                </Label>
              )
            })}
          </RadioGroup>
        </CardContent>
      </Card>

      <RevisaoCorteCard perfil={perfil} />
    </div>
  )
}

/** Corte da fila de revisão (§4.3): grava no blur do campo, com "Limpar" para voltar ao histórico
 *  inteiro. Card próprio porque tem estado e regra de gravação que não são das preferências visuais. */
function RevisaoCorteCard({ perfil }: { perfil: Perfil }) {
  const atualizar = useAtualizarPerfil()
  const salvo = perfil.revisao_desde ?? ""
  const [valor, setValor] = useState(salvo)
  const limpar = useRef<HTMLButtonElement>(null)

  /** Grava a data de corte; "" limpa. Só chama o servidor se mudou de verdade. */
  function gravar(novo: string) {
    if (novo === salvo) return
    setValor(novo)
    atualizar.mutate(
      { revisao_desde: novo || null },
      {
        onSuccess: () => {
          toast.success(
            novo
              ? "Data de início da revisão atualizada."
              : "Todo o histórico volta a pedir revisão."
          )
        },
        onError: (err) => {
          setValor(salvo)
          toast.error(err.message)
        },
      }
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Revisão de transações</CardTitle>
        <CardDescription>
          Transações anteriores a esta data não entram na fila de revisão — elas
          não são marcadas como revisadas, apenas deixam de ser cobradas. Deixe
          em branco para revisar todo o histórico.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="revisao-desde">Revisar a partir de</Label>
            <Input
              id="revisao-desde"
              type="date"
              className="w-44"
              value={valor}
              onChange={(e) => {
                setValor(e.target.value)
              }}
              // Grava no blur: `type="date"` dispara `onChange` com data ainda pela metade.
              // Clicar em "Limpar" também borra o campo — sem esta guarda a data editada seria
              // gravada em paralelo com o null e, se chegasse depois, ressuscitaria o corte.
              onBlur={(e) => {
                if (e.relatedTarget === limpar.current) return
                gravar(e.target.value)
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.currentTarget.blur()
              }}
            />
          </div>
          {salvo ? (
            <Button
              ref={limpar}
              type="button"
              variant="ghost"
              onClick={() => {
                gravar("")
              }}
            >
              Limpar
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
