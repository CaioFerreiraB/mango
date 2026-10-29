import { useRef, useState } from "react"
import { ExternalLink } from "lucide-react"
import { toast } from "sonner"
import { Link } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
  FieldLabel,
} from "@/components/ui/field"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useMe, useSetupStatus } from "@/lib/api/auth"
import {
  errosTelegram,
  useAcaoTelegram,
  useTelegram,
  useTelegramInstancia,
  type Telegram,
  type Vinculo,
} from "@/lib/api/telegram"
import { formatDateTime } from "@/lib/format"
import { ConfirmacaoTelegram } from "./telegram-confirmacao"
import { TelegramInstanciaForm } from "./telegram-instancia"

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
              onClick={() => {
                acao.mutate(
                  { tipo: "vincular" },
                  {
                    onSuccess: (novo) => {
                      setLink(novo)
                    },
                    onError: falhou,
                  }
                )
              }}
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
                  onClick={() => {
                    acao.mutate(
                      { tipo: "testar" },
                      {
                        onSuccess: () => {
                          toast.success("Mensagem de teste enviada.")
                        },
                        onError: falhou,
                      }
                    )
                  }}
                >
                  Enviar teste
                </Button>
                <Button
                  variant="ghost"
                  disabled={acao.isPending}
                  onClick={() => {
                    setDesvincular(true)
                  }}
                >
                  Desvincular
                </Button>
              </>
            ) : null}
          </div>
          <SolicitacaoVinculo
            dados={dados}
            link={linkAtual}
            pendente={acao.isPending}
            confirmar={() => {
              if (!dados.solicitacao_id) return
              acao.mutate(
                { tipo: "confirmar", solicitacaoId: dados.solicitacao_id },
                {
                  onSuccess: () => {
                    setLink(undefined)
                    toast.success("Telegram vinculado.")
                  },
                  onError: falhou,
                }
              )
            }}
          />
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
              onCheckedChange={(ativo) => {
                acao.mutate({ tipo: "preferencia", ativo }, { onError: falhou })
              }}
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
          <TelegramInstanciaForm config={instancia.data} />
        )
      ) : null}
      <ConfirmacaoTelegram
        aberto={desvincular}
        pendente={acao.isPending}
        alterar={setDesvincular}
        foco={vincularRef}
        titulo="Desvincular Telegram?"
        acao="Desvincular"
        confirmar={() => {
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
        Seu relatório será desativado e os envios pendentes serão cancelados.
      </ConfirmacaoTelegram>
    </div>
  )
}

function SolicitacaoVinculo({
  dados,
  link,
  pendente,
  confirmar,
}: {
  dados: Telegram
  link?: Vinculo
  pendente: boolean
  confirmar: () => void
}) {
  if (!dados.solicitacao_id) return null
  return (
    <div className="flex flex-col gap-3" aria-live="polite">
      <Separator />
      {dados.candidato ? (
        <CandidatoVinculo
          candidato={dados.candidato}
          confirmar={confirmar}
          desativado={pendente || !dados.ativo}
        />
      ) : (
        <AbrirVinculo link={link} expira={dados.vinculo_expira_em} />
      )}
    </div>
  )
}

function CandidatoVinculo({
  candidato,
  confirmar,
  desativado,
}: {
  candidato: NonNullable<Telegram["candidato"]>
  confirmar: () => void
  desativado: boolean
}) {
  return (
    <>
      <p className="text-sm">
        Foi você? <strong>{candidato.nome || "Usuário Telegram"}</strong>
        {candidato.username ? ` (@${candidato.username})` : ""} · ID{" "}
        {candidato.usuario_id}
      </p>
      <p className="text-sm text-muted-foreground">
        Confirme apenas se esta é a sua conta. Nenhum dado financeiro foi
        enviado.
      </p>
      <Button className="self-start" disabled={desativado} onClick={confirmar}>
        Confirmar minha conta
      </Button>
    </>
  )
}

function AbrirVinculo({
  link,
  expira,
}: {
  link?: Vinculo
  expira?: string | null
}) {
  return (
    <>
      {link ? (
        <Button className="self-start" variant="outline" asChild>
          <a href={link.url} target="_blank" rel="noreferrer">
            Abrir Telegram <ExternalLink data-icon="inline-end" />
          </a>
        </Button>
      ) : null}
      <p className="text-sm text-muted-foreground">
        {link
          ? "Toque em Iniciar no Telegram e volte aqui para confirmar."
          : "Aguardando o início no Telegram. Se não tiver o link, gere um novo."}{" "}
        {expira ? `Válido até ${formatDateTime(expira)}.` : ""}
      </p>
    </>
  )
}
