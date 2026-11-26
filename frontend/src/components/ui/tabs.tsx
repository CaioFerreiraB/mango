"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Tabs as TabsPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function Tabs({
  className,
  orientation = "horizontal",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      className={cn(
        "group/tabs flex gap-2 data-horizontal:flex-col",
        className
      )}
      {...props}
    />
  )
}

const tabsListVariants = cva(
  // flex-wrap: em tela estreita as abas quebram linha em vez de criar rolagem horizontal
  // (Configurações tem até 10 abas). Por isso min-h-8, não h-8.
  "group/tabs-list inline-flex w-fit max-w-full flex-wrap items-center justify-center rounded-lg p-[3px] text-muted-foreground group-data-horizontal/tabs:min-h-8 group-data-vertical/tabs:h-fit group-data-vertical/tabs:flex-col data-[variant=line]:rounded-none",
  {
    variants: {
      variant: {
        default: "bg-muted",
        // gap-y-2: o sublinhado ativo fica 5px abaixo da aba e invadiria a linha de baixo.
        line: "gap-x-1 gap-y-2 bg-transparent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

/** Escritas de estilo fora do hook (o lint de imutabilidade não aceita mutar o que veio de ref). */
function posicionar(ind: HTMLElement, aba: HTMLElement | null) {
  if (!aba) {
    ind.style.opacity = "0"
    return
  }
  ind.style.opacity = "1"
  ind.style.transform = `translate(${aba.offsetLeft}px, ${aba.offsetTop + aba.offsetHeight + 2}px) scaleX(${aba.offsetWidth})`
}
function marcarPronto(ind: HTMLElement) {
  ind.dataset.pronto = ""
}

/** Sublinhado da variante `line` que DESLIZA até a aba ativa (em vez de piscar em cada uma).
 *  Mede a aba ativa e move um traço de 1px escalado — só `transform` (compositor); a primeira
 *  medição não anima. Observa `data-state` (troca de aba) e o tamanho da lista (quebra de linha). */
function useIndicador(
  ativo: boolean,
  lista: React.RefObject<HTMLDivElement | null>,
  traco: React.RefObject<HTMLSpanElement | null>
) {
  React.useLayoutEffect(() => {
    const el = lista.current
    const ind = traco.current
    if (!ativo || !el || !ind) return
    const medir = () =>
      posicionar(
        ind,
        el.querySelector<HTMLElement>(
          '[data-slot="tabs-trigger"][data-state="active"]'
        )
      )
    medir()
    // Liga a transição só depois do 1º posicionamento (sem deslizar do canto ao montar).
    const raf = requestAnimationFrame(() => marcarPronto(ind))
    const mo = new MutationObserver(medir)
    mo.observe(el, {
      attributes: true,
      subtree: true,
      attributeFilter: ["data-state"],
    })
    const ro = new ResizeObserver(medir)
    ro.observe(el)
    return () => {
      cancelAnimationFrame(raf)
      mo.disconnect()
      ro.disconnect()
    }
  }, [ativo, lista, traco])
}

function TabsList({
  className,
  variant = "default",
  children,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants>) {
  const lista = React.useRef<HTMLDivElement>(null)
  const traco = React.useRef<HTMLSpanElement>(null)
  const linha = variant === "line"
  useIndicador(linha, lista, traco)
  return (
    <TabsPrimitive.List
      ref={lista}
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(
        tabsListVariants({ variant }),
        linha && "relative",
        className
      )}
      {...props}
    >
      {children}
      {linha ? (
        <span
          ref={traco}
          aria-hidden
          className="pointer-events-none absolute top-0 left-0 h-0.5 w-px origin-left rounded-full bg-primary opacity-0 data-pronto:transition-transform data-pronto:duration-300 data-pronto:ease-(--ease-out) motion-reduce:transition-none"
        />
      ) : null}
    </TabsPrimitive.List>
  )
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "relative inline-flex min-h-[calc(2rem-7px)] flex-1 items-center justify-center gap-1.5 rounded-md border border-transparent px-1.5 py-0.5 text-sm font-medium whitespace-nowrap text-foreground/60 transition-[color,background-color,box-shadow] duration-150 group-data-vertical/tabs:w-full group-data-vertical/tabs:justify-start hover:text-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-1 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50 has-data-[icon=inline-end]:pr-1 has-data-[icon=inline-start]:pl-1 dark:text-muted-foreground dark:hover:text-foreground group-data-[variant=default]/tabs-list:data-active:shadow-sm group-data-[variant=line]/tabs-list:data-active:shadow-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        // line: largura natural — esticadas (flex-1) as abas se espalham quando a lista quebra linha.
        "group-data-[variant=line]/tabs-list:flex-none group-data-[variant=line]/tabs-list:bg-transparent group-data-[variant=line]/tabs-list:data-active:bg-transparent dark:group-data-[variant=line]/tabs-list:data-active:border-transparent dark:group-data-[variant=line]/tabs-list:data-active:bg-transparent",
        "data-active:bg-card data-active:text-foreground dark:data-active:border-input dark:data-active:bg-input/30 dark:data-active:text-foreground",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      // Troca de aba = fade curto do conteúdo novo (frequente: sem deslocamento, sem stagger).
      className={cn(
        "flex-1 text-sm outline-none data-[state=active]:animate-[entrada-fade_200ms_ease-out] motion-reduce:animate-none",
        className
      )}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants }
