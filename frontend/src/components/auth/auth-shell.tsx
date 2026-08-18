import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Card } from "@/components/ui/card"
import { ilustracao, type Cena } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

/** Shell das telas públicas (setup, convite, login, recuperação): painel de marca tintado com o
 *  mascote em sangria + painel de formulário. Empilha no mobile (logo → mascote → texto), duas
 *  colunas a partir de `md` (texto à esquerda, mascote na base). Sem sessão não há avatar
 *  escolhido, então a cena resolve no `AVATAR_PADRAO` (DESIGN.md §Illustrations).
 *  `cenaDesktop` troca a ilustração a partir de `md`, quando a cena do mobile não cabe bem
 *  na coluna larga. No desktop o mascote cresce para ocupar a sobra vertical da coluna (formulários
 *  longos, como o setup, deixariam um vão enorme com altura fixa). */
export function AuthShell({
  cena,
  cenaDesktop,
  titulo,
  descricao,
  icone: Icone,
  children,
}: {
  cena: Cena
  cenaDesktop?: Cena
  titulo: ReactNode
  descricao: ReactNode
  icone: LucideIcon
  children: ReactNode
}) {
  return (
    <main className="flex min-h-svh items-center justify-center bg-sidebar p-4 md:p-6">
      <Card className="w-full max-w-4xl gap-0 overflow-hidden py-0 md:grid md:grid-cols-[1.1fr_1fr]">
        <div className="relative flex flex-col gap-6 bg-primary/5 p-6 md:p-8">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(var(--primary)_1px,transparent_1px)] [background-size:16px_16px] opacity-[0.08]"
          />
          <div className="relative z-10 flex items-center justify-center gap-2 md:justify-start">
            <img
              src="/illustrations/avatars/logo/mango-logo.png"
              alt=""
              className="size-8 shrink-0 object-contain"
            />
            <span className="text-base font-semibold tracking-tight">
              mango
            </span>
          </div>

          <div className="relative z-10 order-2 flex flex-col gap-2 text-center md:order-1 md:text-left">
            <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
              {titulo}
            </h1>
            <p className="text-sm text-muted-foreground">{descricao}</p>
          </div>

          <div className="order-1 flex h-48 items-end justify-center md:order-2 md:mt-auto md:-mb-8 md:h-auto md:min-h-72 md:flex-1">
            <img
              src={ilustracao(null, cena)}
              alt=""
              className={cn(
                "pointer-events-none h-full max-w-full object-contain object-bottom",
                cenaDesktop && "md:hidden"
              )}
            />
            {cenaDesktop ? (
              <img
                src={ilustracao(null, cenaDesktop)}
                alt=""
                className="pointer-events-none hidden h-full max-w-full object-contain object-bottom md:block"
              />
            ) : null}
          </div>
        </div>

        <div className="flex flex-col justify-center gap-5 p-6 md:p-8">
          <span className="hidden size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground md:flex">
            <Icone className="size-5" aria-hidden />
          </span>
          {children}
        </div>
      </Card>
    </main>
  )
}
