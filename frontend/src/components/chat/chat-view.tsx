import {
  ArrowLeftIcon,
  ArrowUpIcon,
  CheckIcon,
  CopyIcon,
  HistoryIcon,
  Maximize2Icon,
  Minimize2Icon,
  MoreHorizontalIcon,
  PencilIcon,
  RefreshCwIcon,
  SquareIcon,
  SquarePenIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { ChatMarkdown } from "@/components/chat/chat-markdown"
import { useCopiar } from "@/hooks/use-copiar"
import { useChat } from "@/components/chat/use-chat"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group"
import { Message, MessageContent, MessageFooter } from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Skeleton } from "@/components/ui/skeleton"
import { useMe } from "@/lib/api/auth"
import {
  type ConversaResumo,
  type MensagemChat,
  type Proposta,
  ErroHttp,
  useConversa,
  useConversas,
  useDecidirProposta,
  useExcluirConversa,
  usePreferenciaIa,
  useRenomearConversa,
} from "@/lib/api/chat"
import { ilustracao } from "@/lib/illustrations"
import { cn } from "@/lib/utils"

const SUGESTOES = [
  "Quanto gastei este mês?",
  "Quais assinaturas eu pago hoje?",
  "Como estão meus orçamentos?",
  "Resuma meus investimentos",
]

type Variante = "painel" | "pagina"

/**
 * Chat completo (cabeçalho, mensagens, composer). O painel do desktop e a página `/chat` usam o
 * mesmo componente; só as ações do cabeçalho mudam (`acoes`).
 */
export function ChatView({
  variante,
  acoes,
  voltar,
}: {
  variante: Variante
  acoes?: React.ReactNode
  voltar?: () => void
}) {
  const pref = usePreferenciaIa()
  const pronto = Boolean(pref.data?.disponivel && pref.data.ativa)
  const { conversaId, abrirConversa, envio } = useChat()
  const conversa = useConversa(pronto ? conversaId : null, !envio?.ativo)
  const conversas = useConversas(pronto)
  // Conversa lembrada que expirou (7 dias) ou foi excluída em outra aba: começa uma nova.
  // Falha de rede/5xx mantém a seleção e oferece tentar de novo.
  const perdida =
    conversa.error instanceof ErroHttp && conversa.error.status === 404
  useEffect(() => {
    if (perdida) abrirConversa(null)
  }, [perdida, abrirConversa])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-1 border-b px-2">
        {voltar ? (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={voltar}
            aria-label="Voltar"
          >
            <ArrowLeftIcon />
          </Button>
        ) : null}
        <h2 className="min-w-0 flex-1 truncate px-1.5 text-sm font-medium">
          {conversaId !== null ? (conversa.data?.titulo ?? "…") : "Assistente"}
        </h2>
        {pronto ? (
          <>
            <Historico
              conversas={conversas.data ?? []}
              atual={conversaId}
              onEscolher={abrirConversa}
              bloqueado={Boolean(envio?.ativo)}
            />
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Nova conversa"
              title="Nova conversa"
              disabled={Boolean(envio?.ativo) || conversaId === null}
              onClick={() => abrirConversa(null)}
            >
              <SquarePenIcon />
            </Button>
            {conversaId !== null && conversa.data ? (
              <MenuConversa
                id={conversaId}
                titulo={conversa.data.titulo}
                bloqueado={Boolean(envio?.ativo || conversa.data.executando)}
              />
            ) : null}
          </>
        ) : null}
        {acoes}
      </header>

      {pref.isPending ? (
        <div className="space-y-3 p-4">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : !pref.data?.disponivel ? (
        <Aviso
          titulo="A conversa com IA não está ligada"
          texto="Quem administra o Mango liga a IA e escolhe o provedor em Configurações → Inteligência artificial."
        />
      ) : !pref.data.ativa ? (
        <Aviso
          titulo="Ative a conversa com a IA"
          texto={`Suas mensagens e os dados consultados vão para o provedor ${
            pref.data.provedor === "axon" ? "Axon" : "configurado"
          }. O histórico fica cifrado por sete dias.`}
          acao
        />
      ) : conversa.isError && !conversa.data && !perdida ? (
        <div className="flex flex-1 items-center justify-center p-6">
          <Falha
            mensagem={conversa.error.message}
            onTentar={() => void conversa.refetch()}
          />
        </div>
      ) : (
        <Conversa
          key={conversaId ?? "nova"}
          mensagens={conversaId !== null ? conversa.data?.mensagens : []}
          proposta={conversa.data?.proposta ?? null}
          executandoNoServidor={Boolean(
            conversa.data?.executando && !envio?.ativo
          )}
          carregando={conversaId !== null && conversa.isPending}
          variante={variante}
        />
      )}
    </div>
  )
}

function Aviso({
  titulo,
  texto,
  acao,
}: {
  titulo: string
  texto: string
  acao?: boolean
}) {
  const me = useMe()
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <img
        src={ilustracao(me.data?.avatar, "default")}
        alt=""
        className="size-28 object-contain"
      />
      <h3 className="text-base font-semibold text-balance">{titulo}</h3>
      <p className="max-w-xs text-sm text-pretty text-muted-foreground">
        {texto}
      </p>
      {acao ? (
        <Button asChild size="sm">
          <Link to="/configuracoes?aba=ia">Abrir configurações</Link>
        </Button>
      ) : null}
    </div>
  )
}

function Conversa({
  mensagens,
  proposta,
  executandoNoServidor,
  carregando,
  variante,
}: {
  mensagens: MensagemChat[] | undefined
  proposta: Proposta | null
  executandoNoServidor: boolean
  carregando: boolean
  variante: Variante
}) {
  const { envio, enviar, regenerar, parar, conversaId } = useChat()
  const doEnvio = envio && envio.conversaId === conversaId ? envio : null
  let lista = mensagens ?? []
  // Regenerando: a resposta antiga some enquanto a nova é gerada.
  if (doEnvio?.ativo && doEnvio.pedido === null) {
    const ultimoPedido = lista.findLastIndex((m) => m.papel === "user")
    lista = lista.slice(0, ultimoPedido + 1)
  }
  const ultima = lista.at(-1)
  const ultimaResposta = ultima?.papel === "assistant" ? ultima.id : null
  // O pedido enviado já voltou do servidor (a conversa recarrega durante o stream)?
  const pedidoSalvo =
    doEnvio?.pedido != null &&
    ultima?.papel === "user" &&
    ultima.conteudo === doEnvio.pedido
  // Tentar de novo: pedido gravado (ou regeneração) → regenerar; não gravado (ex.: cota) → reenviar.
  const tentar = !doEnvio
    ? undefined
    : doEnvio.pedido !== null && !pedidoSalvo
      ? () => enviar(doEnvio.pedido!)
      : conversaId !== null
        ? regenerar
        : undefined
  const ocupado = Boolean(envio?.ativo) || executandoNoServidor
  const vazio = !carregando && lista.length === 0 && !doEnvio

  return (
    <>
      <MessageScrollerProvider autoScroll defaultScrollPosition="end">
        <MessageScroller className="flex-1">
          <MessageScrollerViewport aria-label="Mensagens">
            <MessageScrollerContent
              className={cn(
                "mx-auto w-full gap-5 px-4 py-5",
                variante === "pagina" && "max-w-3xl"
              )}
            >
              {carregando ? (
                <div className="space-y-3">
                  <Skeleton className="ml-auto h-9 w-1/2" />
                  <Skeleton className="h-4 w-5/6" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              ) : null}
              {vazio ? <Boasvindas onSugestao={enviar} /> : null}
              {lista.map((m) => (
                <MessageScrollerItem
                  key={m.id}
                  messageId={String(m.id)}
                  scrollAnchor={m.papel === "user"}
                >
                  {m.papel === "user" ? (
                    <Pedido texto={m.conteudo} />
                  ) : (
                    <Resposta
                      texto={m.conteudo}
                      podeRegenerar={m.id === ultimaResposta && !ocupado}
                      onRegenerar={regenerar}
                    />
                  )}
                </MessageScrollerItem>
              ))}
              {doEnvio?.pedido && !pedidoSalvo ? (
                <MessageScrollerItem messageId="pendente" scrollAnchor>
                  <Pedido texto={doEnvio.pedido} />
                </MessageScrollerItem>
              ) : null}
              {doEnvio ? (
                <MessageScrollerItem messageId="resposta">
                  {doEnvio.resposta ? (
                    <Resposta texto={doEnvio.resposta} />
                  ) : null}
                  {doEnvio.status ? <Pensando texto={doEnvio.status} /> : null}
                  {doEnvio.erro ? (
                    <Falha mensagem={doEnvio.erro} onTentar={tentar} />
                  ) : null}
                </MessageScrollerItem>
              ) : executandoNoServidor ? (
                <MessageScrollerItem messageId="servidor">
                  <Pensando texto="Ainda respondendo…" />
                </MessageScrollerItem>
              ) : null}
              {proposta && !doEnvio?.ativo ? (
                <MessageScrollerItem
                  messageId={`proposta-${proposta.operacao_id}`}
                >
                  <CartaoProposta proposta={proposta} />
                </MessageScrollerItem>
              ) : null}
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton />
        </MessageScroller>
      </MessageScrollerProvider>
      <Composer
        ocupado={ocupado}
        respondendo={Boolean(envio?.ativo)}
        onEnviar={enviar}
        onParar={parar}
        variante={variante}
      />
    </>
  )
}

function Boasvindas({ onSugestao }: { onSugestao: (texto: string) => void }) {
  const me = useMe()
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 py-6 text-center">
      <img
        src={ilustracao(me.data?.avatar, "hang-loose")}
        alt=""
        className="size-32 object-contain"
      />
      <div className="space-y-1">
        <h3 className="text-lg font-semibold">Como posso ajudar?</h3>
        <p className="text-sm text-pretty text-muted-foreground">
          Pergunte sobre gastos, contas, orçamentos ou investimentos.
        </p>
      </div>
      <div className="flex max-w-md flex-wrap justify-center gap-2">
        {SUGESTOES.map((s) => (
          <Button
            key={s}
            variant="outline"
            size="sm"
            className="h-auto rounded-full py-1.5 font-normal whitespace-normal"
            onClick={() => onSugestao(s)}
          >
            {s}
          </Button>
        ))}
      </div>
    </div>
  )
}

function Pedido({ texto }: { texto: string }) {
  return (
    <Message align="end">
      <MessageContent>
        <Bubble variant="tinted" align="end">
          <BubbleContent className="whitespace-pre-wrap">{texto}</BubbleContent>
        </Bubble>
      </MessageContent>
    </Message>
  )
}

function Resposta({
  texto,
  podeRegenerar,
  onRegenerar,
}: {
  texto: string
  podeRegenerar?: boolean
  onRegenerar?: () => void
}) {
  const { copiado, copiar } = useCopiar()
  return (
    <Message>
      <MessageContent>
        <ChatMarkdown texto={texto} />
        {onRegenerar ? (
          <MessageFooter className="-ml-1.5 gap-0.5 px-0">
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={copiado ? "Copiado" : "Copiar resposta"}
              title="Copiar"
              onClick={() => copiar(texto)}
            >
              {copiado ? <CheckIcon /> : <CopyIcon />}
            </Button>
            {podeRegenerar ? (
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="Gerar a resposta de novo"
                title="Gerar de novo"
                onClick={onRegenerar}
              >
                <RefreshCwIcon />
              </Button>
            ) : null}
          </MessageFooter>
        ) : null}
      </MessageContent>
    </Message>
  )
}

function Pensando({ texto }: { texto: string }) {
  return (
    <p
      role="status"
      aria-live="polite"
      className="mt-2 animate-pulse text-sm text-muted-foreground motion-reduce:animate-none"
    >
      {texto}
    </p>
  )
}

function Falha({
  mensagem,
  onTentar,
}: {
  mensagem: string
  onTentar?: () => void
}) {
  return (
    <div
      role="alert"
      className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm"
    >
      <span className="min-w-0 flex-1">{mensagem}</span>
      {onTentar ? (
        <Button variant="outline" size="xs" onClick={onTentar}>
          <RefreshCwIcon />
          Tentar de novo
        </Button>
      ) : null}
    </div>
  )
}

function CartaoProposta({ proposta }: { proposta: Proposta }) {
  const decidir = useDecidirProposta()
  const ate = new Date(proposta.expira_em).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  })
  // `mutateAsync`: o card desmonta quando a conversa recarrega sem a proposta, e callbacks
  // passados a `mutate` morrem junto com ele.
  const decidirComo = (confirmar: boolean) =>
    decidir.mutateAsync({ id: proposta.operacao_id, confirmar }).then(
      () =>
        toast.success(
          confirmar ? "Alteração aplicada." : "Alteração descartada."
        ),
      (e: Error) => toast.error(e.message)
    )
  return (
    <section
      aria-label="Alteração proposta"
      className="rounded-xl border bg-card p-3 text-sm shadow-xs"
    >
      <p className="font-medium">Confira antes de aplicar</p>
      <p className="mt-1.5 whitespace-pre-line text-muted-foreground">
        {proposta.resumo.replace(/^Confira as alterações\. [^\n]*\n?/, "")}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={decidir.isPending}
          onClick={() => decidirComo(true)}
        >
          Aplicar alteração
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={decidir.isPending}
          onClick={() => decidirComo(false)}
        >
          Descartar
        </Button>
        <span className="ml-auto text-xs text-muted-foreground">
          Vale até {ate}
        </span>
      </div>
    </section>
  )
}

function Composer({
  ocupado,
  respondendo,
  onEnviar,
  onParar,
  variante,
}: {
  ocupado: boolean
  respondendo: boolean
  onEnviar: (texto: string) => void
  onParar: () => void
  variante: Variante
}) {
  const [texto, setTexto] = useState("")
  const ref = useRef<HTMLTextAreaElement>(null)
  const id = useId()

  // Foco ao abrir (painel/página) e de volta ao terminar uma resposta.
  useEffect(() => {
    if (!ocupado) ref.current?.focus({ preventScroll: true })
  }, [ocupado])

  function enviar() {
    const t = texto.trim()
    if (!t || ocupado) return
    onEnviar(t)
    setTexto("")
  }

  return (
    <form
      className={cn(
        "shrink-0 px-3 pt-1 pb-3",
        variante === "pagina" &&
          "mx-auto w-full max-w-3xl pb-[max(0.75rem,env(safe-area-inset-bottom))]"
      )}
      onSubmit={(e) => {
        e.preventDefault()
        enviar()
      }}
    >
      <label htmlFor={id} className="sr-only">
        Mensagem para o assistente
      </label>
      <InputGroup className="rounded-2xl bg-background">
        <InputGroupTextarea
          id={id}
          ref={ref}
          value={texto}
          maxLength={16000}
          rows={1}
          placeholder="Pergunte sobre suas finanças…"
          className="max-h-40 min-h-11 px-3.5 pt-3"
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault()
              enviar()
            }
          }}
        />
        <InputGroupAddon align="block-end" className="justify-between">
          <span className="text-xs text-muted-foreground">
            A IA pode errar. Confira os números importantes.
          </span>
          {respondendo ? (
            <InputGroupButton
              variant="secondary"
              size="icon-sm"
              className="rounded-full"
              aria-label="Parar resposta"
              onClick={onParar}
            >
              <SquareIcon className="fill-current" />
            </InputGroupButton>
          ) : (
            <InputGroupButton
              type="submit"
              variant="default"
              size="icon-sm"
              className="rounded-full"
              aria-label="Enviar"
              disabled={!texto.trim() || ocupado}
            >
              <ArrowUpIcon />
            </InputGroupButton>
          )}
        </InputGroupAddon>
      </InputGroup>
    </form>
  )
}

function grupoDe(iso: string) {
  const dia = new Date(iso)
  const hoje = new Date()
  const ontem = new Date()
  ontem.setDate(hoje.getDate() - 1)
  if (dia.toDateString() === hoje.toDateString()) return "Hoje"
  if (dia.toDateString() === ontem.toDateString()) return "Ontem"
  return "Últimos 7 dias"
}

function Historico({
  conversas,
  atual,
  onEscolher,
  bloqueado,
}: {
  conversas: ConversaResumo[]
  atual: number | null
  onEscolher: (id: number) => void
  bloqueado: boolean
}) {
  const [aberto, setAberto] = useState(false)
  const grupos = new Map<string, ConversaResumo[]>()
  for (const c of conversas) {
    const g = grupoDe(c.atualizado_em)
    grupos.set(g, [...(grupos.get(g) ?? []), c])
  }
  return (
    <Popover open={aberto} onOpenChange={setAberto}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Histórico de conversas"
          title="Histórico"
          disabled={bloqueado}
        >
          <HistoryIcon />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 p-0">
        <Command>
          <CommandInput placeholder="Buscar conversa…" />
          <CommandList className="scrollbar-sutil">
            <CommandEmpty>
              {conversas.length
                ? "Nada encontrado."
                : "Nenhuma conversa nos últimos 7 dias."}
            </CommandEmpty>
            {[...grupos].map(([grupo, itens]) => (
              <CommandGroup key={grupo} heading={grupo}>
                {itens.map((c) => (
                  <CommandItem
                    key={c.id}
                    value={`${c.titulo} ${c.id}`}
                    data-checked={c.id === atual}
                    onSelect={() => {
                      onEscolher(c.id)
                      setAberto(false)
                    }}
                  >
                    <span className="truncate">{c.titulo}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

function MenuConversa({
  id,
  titulo,
  bloqueado,
}: {
  id: number
  titulo: string
  bloqueado: boolean
}) {
  const { abrirConversa } = useChat()
  const renomear = useRenomearConversa()
  const excluir = useExcluirConversa(() => abrirConversa(null))
  const [dialogo, setDialogo] = useState<"renomear" | "excluir" | null>(null)
  const [novo, setNovo] = useState(titulo)
  const formId = useId()
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Mais ações da conversa"
            disabled={bloqueado}
          >
            <MoreHorizontalIcon />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => {
              setNovo(titulo)
              setDialogo("renomear")
            }}
          >
            <PencilIcon />
            Renomear
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onSelect={() => setDialogo("excluir")}
          >
            <Trash2Icon />
            Excluir
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog
        open={dialogo === "renomear"}
        onOpenChange={(o) => !o && setDialogo(null)}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Renomear conversa</DialogTitle>
          </DialogHeader>
          <form
            id={formId}
            onSubmit={(e) => {
              e.preventDefault()
              if (!novo.trim()) return
              renomear.mutate(
                { id, titulo: novo.trim() },
                {
                  onSuccess: () => setDialogo(null),
                  onError: (err) => toast.error(err.message),
                }
              )
            }}
          >
            <Input
              aria-label="Título"
              value={novo}
              maxLength={120}
              autoFocus
              onChange={(e) => setNovo(e.target.value)}
            />
          </form>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialogo(null)}>
              Cancelar
            </Button>
            <Button
              type="submit"
              form={formId}
              disabled={renomear.isPending || !novo.trim()}
            >
              Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={dialogo === "excluir"}
        onOpenChange={(o) => !o && setDialogo(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir esta conversa?</AlertDialogTitle>
            <AlertDialogDescription>
              O histórico é apagado do Mango. Isso não devolve mensagens da cota
              diária.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className={buttonVariants({ variant: "destructive" })}
              onClick={() =>
                excluir.mutate(id, {
                  onError: (err) => toast.error(err.message),
                })
              }
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

/** Ações do cabeçalho no painel do desktop: expandir para `/chat` e fechar. */
export function AcoesPainel({
  onExpandir,
  onFechar,
}: {
  onExpandir: () => void
  onFechar: () => void
}) {
  return (
    <>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Expandir conversa"
        title="Expandir"
        onClick={onExpandir}
      >
        <Maximize2Icon />
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Fechar assistente"
        title="Fechar"
        onClick={onFechar}
      >
        <XIcon />
      </Button>
    </>
  )
}

export function AcaoRecolher({ onRecolher }: { onRecolher: () => void }) {
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Recolher para o painel lateral"
      title="Recolher"
      className="hidden md:inline-flex"
      onClick={onRecolher}
    >
      <Minimize2Icon />
    </Button>
  )
}
