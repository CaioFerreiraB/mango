import {
  DndContext,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  rectSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { ArrowDown, ArrowUp, EyeOff, LayoutGrid } from "lucide-react"
import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type TouchEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react"

import { EmptyState } from "@/components/common/empty-state"
import { Button } from "@/components/ui/button"
import { useMovimentoReduzido } from "@/hooks/use-movimento-reduzido"
import {
  ALTURA_MAX,
  ALTURA_MIN,
  CATALOGO,
  ROTULO_LARGURA,
  ehCompacto,
  encaixarAltura,
  encaixarLargura,
  larguraMinima,
  passoLargura,
  type WidgetLayout,
} from "@/lib/dashboard-layout"
import { cn } from "@/lib/utils"

const TITULO = new Map(CATALOGO.map((w) => [w.id as string, w.titulo]))

/**
 * Colunas por largura de contêiner (container query: janela − sidebar − chat). Só ≥ @4xl a
 * largura salva vale de verdade (grid de 60, via `--largura`); abaixo, ela escolhe um degrau:
 * - @3xl–@4xl (6 colunas): até ⅓ vira ⅓, ¼ e até ½ viram ½, mais largo ocupa a linha;
 * - @xl–@3xl (2 colunas): até ½ vira ½, mais largo ocupa a linha;
 * - abaixo: KPIs dois por linha, o resto na linha toda.
 * Classes estáticas: o Tailwind não enxerga classe montada em runtime.
 */
function spanDe(w: WidgetLayout) {
  const l = w.largura
  return cn(
    ehCompacto(w.id) ? "col-span-1" : "col-span-2",
    l <= 30 ? "@xl:col-span-1" : "@xl:col-span-2",
    l === 15 || (l > 20 && l <= 30)
      ? "@3xl:col-span-3"
      : l <= 20
        ? "@3xl:col-span-2"
        : "@3xl:col-span-6",
    "@4xl:col-span-(--largura)"
  )
}

/**
 * Grade personalizável de uma aba do dashboard. No modo edição: arrastar o card (toque longo no
 * celular) reordena; as bordas direita/inferior (telas largas) mudam largura e altura, encaixando
 * em frações do grid e em passos de 8px.
 */
export function GradeWidgets({
  itens,
  widgets,
  editando,
  bloqueado,
  onAlterar,
  onMover,
  onReordenar,
}: {
  /** Widgets visíveis da aba, na ordem. */
  itens: WidgetLayout[]
  widgets: Record<string, () => ReactNode>
  editando: boolean
  /** Gravação em andamento: controles travados (mudança agora se perderia no fim do save). */
  bloqueado: boolean
  onAlterar: (id: string, patch: Partial<WidgetLayout>) => void
  onMover: (id: string, delta: number) => void
  onReordenar: (de: string, para: string) => void
}) {
  // Mouse: arrasta depois de 4px (clique simples não vira arraste). Toque: segurar 250ms — sem
  // isso, rolar a página por cima de um card começaria um arraste.
  const sensores = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 250, tolerance: 6 },
    })
  )
  const aoSoltar = (e: DragEndEvent) => {
    if (e.over && e.active.id !== e.over.id)
      onReordenar(String(e.active.id), String(e.over.id))
  }

  if (itens.length === 0)
    return (
      <EmptyState
        icon={LayoutGrid}
        title="Nenhuma visualização nesta aba"
        description={
          editando
            ? "Use “Adicionar visualização” para trazer os blocos de volta."
            : "Clique em “Personalizar” e use “Adicionar visualização” para trazer os blocos de volta."
        }
      />
    )

  return (
    // @container: o grid lê a largura disponível (ver spanDe).
    <div className="@container">
      <DndContext
        sensors={sensores}
        collisionDetection={closestCenter}
        onDragEnd={aoSoltar}
      >
        <SortableContext
          items={itens.map((w) => w.id)}
          strategy={rectSortingStrategy}
        >
          {/* @4xl: 59 vãos de 16px (944px) passariam do próprio @4xl (896px) — 12px cabem. */}
          <div className="grid grid-cols-2 gap-3 sm:gap-4 @3xl:grid-cols-6 @4xl:grid-cols-60 @4xl:gap-3">
            {itens.map((w, i) => (
              <Widget
                key={w.id}
                w={w}
                editando={editando}
                bloqueado={bloqueado}
                primeiro={i === 0}
                ultimo={i === itens.length - 1}
                onAlterar={(patch) => onAlterar(w.id, patch)}
                onMover={(delta) => onMover(w.id, delta)}
              >
                {widgets[w.id]?.()}
              </Widget>
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  )
}

/** Moldura de um widget: lugar no grid e, no modo edição, arraste, bordas e barra de controles. */
function Widget({
  w,
  editando,
  bloqueado,
  primeiro,
  ultimo,
  onAlterar,
  onMover,
  children,
}: {
  w: WidgetLayout
  editando: boolean
  bloqueado: boolean
  primeiro: boolean
  ultimo: boolean
  onAlterar: (patch: Partial<WidgetLayout>) => void
  onMover: (delta: number) => void
  children: ReactNode
}) {
  const titulo = TITULO.get(w.id) ?? w.id
  const ativo = editando && !bloqueado
  const reduzido = useMovimentoReduzido()
  const { listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: w.id, disabled: !ativo })
  const ref = useRef<HTMLElement | null>(null)
  // Altura atual do card (para o aria-valuenow da borda inferior na altura automática); medida
  // só no modo edição, que é quando a borda existe.
  const [alturaMedida, setAlturaMedida] = useState(ALTURA_MIN)
  useEffect(() => {
    const el = ref.current
    if (!editando || !el) return
    const ro = new ResizeObserver(([e]) =>
      setAlturaMedida(
        Math.min(
          ALTURA_MAX,
          Math.max(ALTURA_MIN, Math.round(e.borderBoxSize[0].blockSize))
        )
      )
    )
    ro.observe(el)
    return () => ro.disconnect()
  }, [editando])

  function redimensionar(
    e: ReactPointerEvent<HTMLElement>,
    eixo: "x" | "y" | "xy"
  ) {
    const sec = ref.current
    const grade = sec?.parentElement
    if (!sec || !grade || e.button !== 0) return
    // preventDefault no pointerdown também suprime o mousedown de compatibilidade: o arraste do
    // card (MouseSensor) não começa junto.
    e.preventDefault()
    e.stopPropagation()
    const alca = e.currentTarget
    alca.setPointerCapture(e.pointerId)
    const inicio = sec.getBoundingClientRect()
    const larguraGrade = grade.getBoundingClientRect().width
    const gap = parseFloat(getComputedStyle(grade).columnGap) || 0
    const x0 = e.clientX
    const y0 = e.clientY
    const mover = (ev: PointerEvent) => {
      const patch: Partial<WidgetLayout> = {}
      // N colunas de 60 com gap g ocupam N·col + (N−1)·g ⇒ N = (px + g)·60 / (grade + g).
      if (eixo !== "y")
        patch.largura = encaixarLargura(
          ((inicio.width + ev.clientX - x0 + gap) * 60) / (larguraGrade + gap),
          w.id
        )
      if (eixo !== "x")
        patch.altura = encaixarAltura(inicio.height + ev.clientY - y0)
      onAlterar(patch)
    }
    const soltar = () => {
      alca.removeEventListener("pointermove", mover)
      alca.removeEventListener("pointerup", soltar)
      alca.removeEventListener("pointercancel", soltar)
    }
    alca.addEventListener("pointermove", mover)
    alca.addEventListener("pointerup", soltar)
    alca.addEventListener("pointercancel", soltar)
  }

  // Toque numa borda redimensiona; não pode também acordar o TouchSensor (toque longo) do card.
  const pararToque = (e: TouchEvent) => e.stopPropagation()

  // Teclado nas bordas (padrão "window splitter"): ←/→ trocam a fração, ↑/↓ a altura em 40px;
  // Delete/Backspace na borda inferior volta à altura do conteúdo.
  function teclaLargura(e: KeyboardEvent) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return
    e.preventDefault()
    onAlterar({
      largura: passoLargura(w.largura, e.key === "ArrowLeft" ? -1 : 1, w.id),
    })
  }
  function teclaAltura(e: KeyboardEvent<HTMLElement>) {
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault()
      onAlterar({ altura: undefined })
      return
    }
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return
    e.preventDefault()
    const atual = w.altura ?? ref.current?.getBoundingClientRect().height ?? 240
    onAlterar({
      altura: encaixarAltura(atual + (e.key === "ArrowDown" ? 40 : -40)),
    })
  }

  const estilo = {
    transform: CSS.Translate.toString(transform),
    // Reduzir movimento: os vizinhos pulam para o lugar em vez de deslizar (o card arrastado
    // continua seguindo o ponteiro, que é o `transform`).
    transition: reduzido ? undefined : transition,
    "--largura": w.largura,
    ...(w.altura ? { "--altura": `${w.altura}px` } : {}),
  } as CSSProperties

  return (
    <section
      ref={(el) => {
        setNodeRef(el)
        ref.current = el
      }}
      aria-label={titulo}
      style={estilo}
      {...(ativo ? listeners : {})}
      className={cn(
        "group/widget relative min-w-0 @4xl:min-h-(--altura)",
        spanDe(w),
        editando &&
          "cursor-grab rounded-xl outline-2 outline-offset-2 outline-primary/35 outline-dashed active:cursor-grabbing",
        isDragging && "z-20 opacity-80"
      )}
    >
      {/* Conteúdo inerte na edição: um clique num link do card não pode sair da página com o
          rascunho aberto, e o card inteiro vira superfície de arraste. */}
      <div
        className={cn(
          "h-full [&>*]:h-full",
          editando && "pointer-events-none select-none"
        )}
        inert={editando || undefined}
      >
        {children}
      </div>
      {editando ? (
        <>
          <fieldset
            disabled={bloqueado}
            // O arraste do card não começa nos botões (clique neles fica clique).
            onMouseDown={(e) => e.stopPropagation()}
            onTouchStart={(e) => e.stopPropagation()}
            className="absolute -top-3 right-3 z-10 flex h-auto! cursor-default items-center gap-0.5 rounded-lg border bg-popover p-0.5 shadow-sm"
          >
            <span className="hidden px-1.5 text-xs text-muted-foreground tabular-nums @4xl:inline">
              {ROTULO_LARGURA[w.largura] ?? `${w.largura}/60`}
            </span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Ocultar ${titulo}`}
              onClick={() => onAlterar({ visivel: false })}
            >
              <EyeOff aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Mover ${titulo} para trás`}
              disabled={primeiro}
              onClick={() => onMover(-1)}
            >
              <ArrowUp aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Mover ${titulo} para frente`}
              disabled={ultimo}
              onClick={() => onMover(1)}
            >
              <ArrowDown aria-hidden />
            </Button>
          </fieldset>
          {/* Bordas de redimensionar: só onde a largura salva vale (grid de 60, ≥ @4xl). */}
          {!bloqueado ? (
            <div className="hidden @4xl:contents">
              <div
                role="separator"
                aria-orientation="vertical"
                aria-label={`Largura de ${titulo}`}
                aria-valuemin={larguraMinima(w.id)}
                aria-valuemax={60}
                aria-valuenow={w.largura}
                aria-valuetext={ROTULO_LARGURA[w.largura]}
                tabIndex={0}
                onPointerDown={(e) => redimensionar(e, "x")}
                onTouchStart={pararToque}
                onKeyDown={teclaLargura}
                className="group/alca absolute inset-y-6 -right-2.5 z-10 flex w-5 cursor-ew-resize touch-none items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="h-10 w-1.5 rounded-full bg-primary/45 transition-colors group-hover/alca:bg-primary" />
              </div>
              <div
                role="separator"
                aria-orientation="horizontal"
                aria-label={`Altura de ${titulo}`}
                aria-valuemin={ALTURA_MIN}
                aria-valuemax={ALTURA_MAX}
                aria-valuenow={w.altura ?? alturaMedida}
                aria-valuetext={w.altura ? `${w.altura}px` : "automática"}
                tabIndex={0}
                onPointerDown={(e) => redimensionar(e, "y")}
                onTouchStart={pararToque}
                onDoubleClick={() => onAlterar({ altura: undefined })}
                onKeyDown={teclaAltura}
                title="Duplo clique: altura automática"
                className="group/alca absolute inset-x-6 -bottom-2.5 z-10 flex h-5 cursor-ns-resize touch-none items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="h-1.5 w-10 rounded-full bg-primary/45 transition-colors group-hover/alca:bg-primary" />
              </div>
              <div
                aria-hidden
                onPointerDown={(e) => redimensionar(e, "xy")}
                onTouchStart={pararToque}
                onDoubleClick={() => onAlterar({ altura: undefined })}
                className="absolute -right-2.5 -bottom-2.5 z-10 size-5 cursor-nwse-resize touch-none"
              />
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
