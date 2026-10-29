import { useRef, useState } from "react"
import { ExternalLink } from "lucide-react"
import { toast } from "sonner"
import { Link } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useMe, useSetupStatus } from "@/lib/api/auth"
import {
  errosTelegram,
  useAcaoTelegram,
  useTelegram,
  useTelegramInstancia,
  type InstanciaUpdate,
  type TelegramInstancia,
  type Vinculo,
} from "@/lib/api/telegram"
import { formatDateTime } from "@/lib/format"

export function TelegramTab() {
  const me = useMe()
  const setup = useSetupStatus()
  const local = setup.data?.app_mode === "local"
  const administra = me.data?.is_admin === true
  const estado = useTelegram()
  const instancia = useTelegramInstancia(administra)
  const acao = useAcaoTelegram()
  const [link, setLink] = useState<Vinculo>()
  const [desvincular, setDesvincular] = useState(false)
  const vincularRef = useRef<HTMLButtonElement>(null)
  const dados = estado.data

  function falhou(err: Error) {
    toast.error(err.message)
  }

  if (estado.isPending) return <Skeleton className="h-48 max-w-2xl" />
  if (estado.isError || !dados)
    return (
      <Alert variant="destructive">
        <AlertTitle>Não foi possível carregar o Telegram</AlertTitle>
        <AlertDescription>
          <p>{estado.error?.message}</p>
          <Button variant="outline" onClick={() => estado.refetch()}>
            Tentar novamente
          </Button>
        </AlertDescription>
      </Alert>
    )

  const identidade = dados.identidade
  const candidato = dados.candidato
  const linkAtual =
    link?.solicitacao_id === dados.solicitacao_id ? link : undefined
  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>Seu Telegram</CardTitle>
            <Badge variant="secondary">
              {dados.vinculado ? "Vinculado" : "Não vinculado"}
            </Badge>
          </div>
          <CardDescription>
            Receba um resumo das transações que precisam de revisão após a
            sincronização diária.
          </CardDescription>
        </CardHeader>
        <CardContent
          className="flex flex-col gap-4 wrap-anywhere"
          aria-busy={acao.isPending}
        >
          {!dados.ativo ? (
            <Alert>
              <AlertTitle>
                {dados.configurado
                  ? "Integração pausada"
                  : "Bot ainda não configurado"}
              </AlertTitle>
              <AlertDescription>
                {administra
                  ? "Configure e ative o bot abaixo para vincular seu Telegram."
                  : "O administrador precisa configurar e ativar o bot desta instalação."}
              </AlertDescription>
            </Alert>
          ) : null}
          {dados.erro ? (
            <Alert variant="destructive">
              <AlertDescription>
                {errosTelegram[dados.erro] ??
                  "Não foi possível concluir a rotina. Teste a conexão novamente."}
              </AlertDescription>
            </Alert>
          ) : null}
          {identidade ? (
            <p className="text-sm">
              Vinculado a{" "}
              <strong>{identidade.nome || "Usuário Telegram"}</strong>
              {identidade.username ? ` (@${identidade.username})` : ""} · ID{" "}
              {identidade.usuario_id}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Abra o bot pelo link e confirme sua identidade aqui no Mango.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              ref={vincularRef}
              variant={dados.vinculado ? "outline" : "default"}
              disabled={!dados.ativo || acao.isPending}
              onClick={() =>
                acao.mutate(
                  { tipo: "vincular" },
                  { onSuccess: (novo) => setLink(novo), onError: falhou }
                )
              }
            >
              {dados.solicitacao_id
                ? "Gerar novo link"
                : dados.vinculado
                  ? "Trocar vínculo"
                  : "Vincular Telegram"}
            </Button>
            {dados.vinculado ? (
              <>
                <Button
                  variant="outline"
                  disabled={!dados.ativo || acao.isPending}
                  onClick={() =>
                    acao.mutate(
                      { tipo: "testar" },
                      {
                        onSuccess: () =>
                          toast.success("Mensagem de teste enviada."),
                        onError: falhou,
                      }
                    )
                  }
                >
                  Enviar teste
                </Button>
                <Button
                  variant="ghost"
                  disabled={acao.isPending}
                  onClick={() => setDesvincular(true)}
                >
                  Desvincular
                </Button>
              </>
            ) : null}
          </div>
          {dados.solicitacao_id ? (
            <div className="flex flex-col gap-3" aria-live="polite">
              <Separator />
              {candidato ? (
                <>
                  <p className="text-sm">
                    Foi você?{" "}
                    <strong>{candidato.nome || "Usuário Telegram"}</strong>
                    {candidato.username ? ` (@${candidato.username})` : ""} · ID{" "}
                    {candidato.usuario_id}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Confirme apenas se esta é a sua conta. Nenhum dado
                    financeiro foi enviado.
                  </p>
                  <Button
                    className="self-start"
                    disabled={acao.isPending || !dados.ativo}
                    onClick={() =>
                      acao.mutate(
                        {
                          tipo: "confirmar",
                          solicitacaoId: dados.solicitacao_id!,
                        },
                        {
                          onSuccess: () => {
                            setLink(undefined)
                            toast.success("Telegram vinculado.")
                          },
                          onError: falhou,
                        }
                      )
                    }
                  >
                    Confirmar minha conta
                  </Button>
                </>
              ) : (
                <>
                  {linkAtual ? (
                    <Button className="self-start" variant="outline" asChild>
                      <a href={linkAtual.url} target="_blank" rel="noreferrer">
                        Abrir Telegram <ExternalLink data-icon="inline-end" />
                      </a>
                    </Button>
                  ) : null}
                  <p className="text-sm text-muted-foreground">
                    {linkAtual
                      ? "Toque em Iniciar no Telegram e volte aqui para confirmar."
                      : "Aguardando o início no Telegram. Se não tiver o link, gere um novo."}{" "}
                    Válido até {formatDateTime(dados.vinculo_expira_em!)}.
                  </p>
                </>
              )}
            </div>
          ) : null}
          <Separator />
          <Field orientation="horizontal" data-disabled={!dados.vinculado}>
            <FieldContent>
              <FieldLabel htmlFor="telegram-relatorio">
                Receber relatório diário de pendências
              </FieldLabel>
              <FieldDescription id="telegram-relatorio-desc">
                Quantidade e até dez transações, com data, descrição e valor,
                enviadas ao Telegram. Sem pendências, nenhuma mensagem.
              </FieldDescription>
            </FieldContent>
            <Switch
              id="telegram-relatorio"
              aria-describedby="telegram-relatorio-desc"
              checked={dados.notif_nao_revisadas}
              disabled={
                !dados.vinculado ||
                acao.isPending ||
                (!dados.ativo && !dados.notif_nao_revisadas)
              }
              onCheckedChange={(ativo) =>
                acao.mutate({ tipo: "preferencia", ativo }, { onError: falhou })
              }
            />
          </Field>
          <div className="flex flex-col gap-1 text-sm text-muted-foreground">
            <p>
              {dados.sync_automatico
                ? `Sincronização diária às ${dados.sync_horario.slice(0, 5)} (Brasília).`
                : "A sincronização automática está desativada."}
            </p>
            <Link
              className="self-start underline underline-offset-4"
              to="/configuracoes?aba=conexoes"
            >
              Ver configuração da sincronização em Conexões
            </Link>
            {dados.proxima_rotina ? (
              <p>
                Próxima rotina prevista: {formatDateTime(dados.proxima_rotina)}.
              </p>
            ) : null}
            {dados.ultimo_envio_em ? (
              <p>
                Último relatório enviado:{" "}
                {formatDateTime(dados.ultimo_envio_em)}.
              </p>
            ) : null}
            {local ? (
              <p>
                O Mango precisa estar aberto. Se perder o horário, a rotina do
                dia acontece ao abrir.
              </p>
            ) : null}
            <p>
              O resumo oculta lançamentos futuros e pagamentos de fatura e
              respeita sua data de início da revisão.
            </p>
          </div>
        </CardContent>
      </Card>
      {administra ? (
        instancia.isPending ? (
          <Skeleton className="h-48" />
        ) : instancia.isError || !instancia.data ? (
          <Alert variant="destructive">
            <AlertTitle>
              Não foi possível carregar a configuração do bot
            </AlertTitle>
            <AlertDescription>
              <Button variant="outline" onClick={() => instancia.refetch()}>
                Tentar novamente
              </Button>
            </AlertDescription>
          </Alert>
        ) : (
          <InstanciaForm config={instancia.data} />
        )
      ) : null}
      <AlertDialog
        open={desvincular}
        onOpenChange={(aberto) => {
          if (!acao.isPending) setDesvincular(aberto)
        }}
      >
        <AlertDialogContent
          onCloseAutoFocus={(e) => {
            e.preventDefault()
            vincularRef.current?.focus()
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>Desvincular Telegram?</AlertDialogTitle>
            <AlertDialogDescription>
              Seu relatório será desativado e os envios pendentes serão
              cancelados.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={acao.isPending}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={acao.isPending}
              onClick={(e) => {
                e.preventDefault()
                acao.mutate(
                  { tipo: "desvincular" },
                  {
                    onSuccess: () => {
                      setLink(undefined)
                      setDesvincular(false)
                      toast.success("Telegram desvinculado.")
                    },
                    onError: falhou,
                  }
                )
              }}
            >
              Desvincular
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function InstanciaForm({ config }: { config: TelegramInstancia }) {
  const acao = useAcaoTelegram()
  const [token, setToken] = useState("")
  const [troca, setTroca] = useState<InstanciaUpdate>()
  const [remover, setRemover] = useState(false)
  const tokenRef = useRef<HTMLInputElement>(null)
  function falhou(err: Error) {
    toast.error(err.message)
  }
  function salvar(dados: InstanciaUpdate) {
    acao.mutate(
      { tipo: "instancia", dados },
      {
        onSuccess: () => {
          if (dados.token) setToken("")
          setTroca(undefined)
          toast.success("Configuração salva.")
        },
        onError: (err) => {
          if (err.cause === 409 && err.message.startsWith("outro bot:"))
            setTroca(dados)
          else falhou(err)
        },
      }
    )
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bot desta instalação</CardTitle>
        <CardDescription>
          Um bot exclusivo para todos os usuários, com vínculos e relatórios
          individuais.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5" aria-busy={acao.isPending}>
        <p className="text-sm text-muted-foreground">
          Crie um bot no{" "}
          <a
            className="underline underline-offset-4"
            href="https://t.me/BotFather"
            target="_blank"
            rel="noreferrer"
          >
            BotFather
          </a>{" "}
          com /newbot e cole o token. Use um bot sem webhook, exclusivo para
          esta instalação.
        </p>
        <p className="text-sm">
          {config.configurado
            ? `Bot configurado: @${config.bot_username}`
            : "Nenhum token salvo."}
        </p>
        {config.erro ? (
          <Alert variant="destructive">
            <AlertDescription>
              {errosTelegram[config.erro] ?? "Falha na conexão do bot."}
            </AlertDescription>
          </Alert>
        ) : null}
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            salvar({ token })
          }}
        >
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="telegram-token">
                {config.configurado ? "Novo token" : "Token do bot"}
              </FieldLabel>
              <Input
                ref={tokenRef}
                id="telegram-token"
                maxLength={256}
                aria-describedby="telegram-token-desc"
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                disabled={acao.isPending}
              />
              <FieldDescription id="telegram-token-desc">
                Guardado cifrado. O Mango nunca exibe o token salvo.
              </FieldDescription>
            </Field>
          </FieldGroup>
          <Button
            type="submit"
            className="self-start"
            disabled={acao.isPending || !token}
          >
            {acao.isPending ? "Salvando…" : "Salvar e validar token"}
          </Button>
        </form>
        <p className="text-sm text-muted-foreground">
          O botão “Revisar no Mango” usa automaticamente o endereço desta
          instalação.
        </p>
        <Separator />
        <FieldGroup>
          <Field orientation="horizontal" data-disabled={!config.configurado}>
            <FieldContent>
              <FieldLabel htmlFor="telegram-ativo">
                Ativar integração Telegram
              </FieldLabel>
              <FieldDescription id="telegram-ativo-desc">
                Permite vincular contas e entregar relatórios.
              </FieldDescription>
            </FieldContent>
            <Switch
              id="telegram-ativo"
              aria-describedby="telegram-ativo-desc"
              checked={config.ativo}
              disabled={!config.configurado || acao.isPending}
              onCheckedChange={(ativo) => salvar({ ativo })}
            />
          </Field>
        </FieldGroup>
        {config.configurado ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={acao.isPending}
              onClick={() =>
                acao.mutate(
                  { tipo: "testar-instancia" },
                  {
                    onSuccess: () =>
                      toast.success("Token válido e bot disponível."),
                    onError: falhou,
                  }
                )
              }
            >
              Validar conexão do bot
            </Button>
            <Button
              variant="ghost"
              disabled={acao.isPending}
              onClick={() => setRemover(true)}
            >
              Remover bot
            </Button>
          </div>
        ) : null}
        <AlertDialog
          open={!!troca}
          onOpenChange={(aberto) => {
            if (!aberto && !acao.isPending) setTroca(undefined)
          }}
        >
          <AlertDialogContent
            onCloseAutoFocus={(e) => {
              e.preventDefault()
              tokenRef.current?.focus()
            }}
          >
            <AlertDialogHeader>
              <AlertDialogTitle>
                Substituir o bot da instalação?
              </AlertDialogTitle>
              <AlertDialogDescription>
                Todos os vínculos serão removidos e os usuários precisarão
                vincular o Telegram novamente. Os relatórios pendentes serão
                cancelados.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={acao.isPending}>
                Cancelar
              </AlertDialogCancel>
              <AlertDialogAction
                disabled={acao.isPending}
                onClick={(e) => {
                  e.preventDefault()
                  if (troca) salvar({ ...troca, confirmar_troca_bot: true })
                }}
              >
                Substituir bot
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <AlertDialog
          open={remover}
          onOpenChange={(aberto) => {
            if (!acao.isPending) setRemover(aberto)
          }}
        >
          <AlertDialogContent
            onCloseAutoFocus={(e) => {
              e.preventDefault()
              tokenRef.current?.focus()
            }}
          >
            <AlertDialogHeader>
              <AlertDialogTitle>Remover o bot?</AlertDialogTitle>
              <AlertDialogDescription>
                O token e todos os vínculos serão removidos. A sincronização
                automática continuará com a configuração atual.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={acao.isPending}>
                Cancelar
              </AlertDialogCancel>
              <AlertDialogAction
                disabled={acao.isPending}
                onClick={(e) => {
                  e.preventDefault()
                  acao.mutate(
                    { tipo: "remover-instancia" },
                    {
                      onSuccess: () => {
                        setToken("")
                        setRemover(false)
                        toast.success("Bot removido.")
                      },
                      onError: falhou,
                    }
                  )
                }}
              >
                Remover bot
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  )
}
