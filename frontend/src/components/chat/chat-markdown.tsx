import { CheckIcon, CopyIcon, ImageIcon } from "lucide-react"
import { memo } from "react"
import Markdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

import { Button } from "@/components/ui/button"
import { useCopiar } from "@/hooks/use-copiar"

function BlocoCodigo({ children }: { children?: React.ReactNode }) {
  const { copiado, copiar } = useCopiar()
  return (
    <div className="group/code relative">
      <pre className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs leading-relaxed">
        {children}
      </pre>
      <Button
        variant="ghost"
        size="icon-xs"
        className="absolute top-1.5 right-1.5 opacity-0 group-hover/code:opacity-100 focus-visible:opacity-100"
        aria-label={copiado ? "Copiado" : "Copiar código"}
        onClick={(e) =>
          copiar(
            e.currentTarget.parentElement?.querySelector("pre")?.textContent ??
              ""
          )
        }
      >
        {copiado ? <CheckIcon /> : <CopyIcon />}
      </Button>
    </div>
  )
}

// Sem typography plugin: cada elemento recebe o mínimo de ritmo e hierarquia. `node` (AST do
// react-markdown) não pode chegar ao DOM.
function semNode<T extends { node?: unknown }>(props: T): Omit<T, "node"> {
  const resto = { ...props }
  delete resto.node
  return resto
}

function el<T extends keyof React.JSX.IntrinsicElements>(
  Tag: T,
  className: string,
  extra?: React.ComponentProps<T>
) {
  return function Elemento(
    props: React.ComponentProps<T> & { node?: unknown }
  ) {
    const Comp = Tag as React.ElementType
    return <Comp className={className} {...extra} {...semNode(props)} />
  }
}

const componentes: Components = {
  p: el("p", "leading-relaxed"),
  ul: el("ul", "list-disc space-y-1 pl-5"),
  ol: el("ol", "list-decimal space-y-1 pl-5"),
  li: el("li", "pl-0.5 leading-relaxed"),
  h1: el("h3", "text-base font-semibold"),
  h2: el("h3", "text-base font-semibold"),
  h3: el("h4", "font-semibold"),
  h4: el("h4", "font-semibold"),
  strong: el("strong", "font-semibold"),
  blockquote: el(
    "blockquote",
    "border-l-2 border-border pl-3 text-muted-foreground"
  ),
  th: el("th", "border-b bg-muted/50 px-2.5 py-1.5 text-left font-medium"),
  td: el("td", "border-b px-2.5 py-1.5"),
  hr: el("hr", "border-border"),
  // Links externos sempre em outra aba; `javascript:` já é removido pelo react-markdown.
  a: el("a", "text-accent-ink underline underline-offset-2", {
    target: "_blank",
    rel: "noopener noreferrer",
  }),
  code: (props) => {
    const { className, ...p } = semNode(props)
    return (
      <code
        className={
          className ??
          "rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] [pre_&]:bg-transparent [pre_&]:p-0"
        }
        {...p}
      />
    )
  },
  pre: ({ children }) => <BlocoCodigo>{children}</BlocoCodigo>,
  // Nunca carregar imagem remota sozinha: `![x](https://…?saldo=…)` vazaria dados sem clique
  // (prompt injection via texto de banco). Vira link explícito.
  img: ({ src, alt }) =>
    typeof src === "string" && src ? (
      <a
        href={src}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-accent-ink underline underline-offset-2"
      >
        <ImageIcon className="size-3.5" aria-hidden />
        {alt ? `Imagem: ${alt}` : "Imagem"}
      </a>
    ) : null,
  table: (props) => (
    <div className="overflow-x-auto rounded-lg border">
      <table
        className="w-full text-xs tabular-nums [&_tr:last-child_td]:border-b-0"
        {...semNode(props)}
      />
    </div>
  ),
}

/** Resposta do assistente: GFM sem HTML bruto (texto de banco/LLM nunca vira marcação). */
export const ChatMarkdown = memo(function ChatMarkdown({
  texto,
}: {
  texto: string
}) {
  return (
    <div className="flex min-w-0 flex-col gap-3 text-sm wrap-break-word">
      <Markdown remarkPlugins={[remarkGfm]} components={componentes} skipHtml>
        {texto}
      </Markdown>
    </div>
  )
})
