import { useRef, useState } from "react"
import { toast } from "sonner"

import { Alert, AlertDescription } from "@/components/ui/alert"
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
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import {
  errosTelegram,
  useAcaoTelegram,
  type InstanciaUpdate,
  type TelegramInstancia,
} from "@/lib/api/telegram"
import { ConfirmacaoTelegram } from "./telegram-confirmacao"

function falhou(err: Error) {
  toast.error(err.message)
}

function useFormularioBot() {
  const acao = useAcaoTelegram()
  const [token, setToken] = useState("")
  const [troca, setTroca] = useState<InstanciaUpdate>()
  const [remover, setRemover] = useState(false)
  const tokenRef = useRef<HTMLInputElement>(null)
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
  function removerBot() {
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
  }
  return {
    acao,
    token,
    setToken,
    troca,
    setTroca,
    remover,
    setRemover,
    tokenRef,
    salvar,
    removerBot,
  }
}

type FormularioBot = ReturnType<typeof useFormularioBot>
type CamposBot = { config: TelegramInstancia; form: FormularioBot }

export function TelegramInstanciaForm({
  config,
}: {
  config: TelegramInstancia
}) {
  const form = useFormularioBot()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bot desta instalação</CardTitle>
        <CardDescription>
          Um bot exclusivo para todos os usuários, com vínculos e relatórios
          individuais.
        </CardDescription>
      </CardHeader>
      <CardContent
        className="flex flex-col gap-5"
        aria-busy={form.acao.isPending}
      >
        <EstadoBot config={config} />
        <TokenBot config={config} form={form} />
        <p className="text-sm text-muted-foreground">
          O botão “Revisar no Mango” usa automaticamente o endereço desta
          instalação. Em endereços locais (localhost), o relatório chega sem o
          botão.
        </p>
        <Separator />
        <AtivacaoBot config={config} form={form} />
        {config.configurado ? <AcoesBot form={form} /> : null}
        <ConfirmacoesBot form={form} />
      </CardContent>
    </Card>
  )
}

function EstadoBot({ config }: { config: TelegramInstancia }) {
  return (
    <>
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
        com /newbot e cole o token. Use um bot sem webhook, exclusivo para esta
        instalação.
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
    </>
  )
}

function TokenBot({ config, form }: CamposBot) {
  const { tokenRef, token, setToken, acao, salvar } = form
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        salvar({ token: token })
      }}
    >
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
          onChange={(e) => {
            setToken(e.target.value)
          }}
          disabled={acao.isPending}
        />
        <FieldDescription id="telegram-token-desc">
          Guardado cifrado. O Mango nunca exibe o token salvo.
        </FieldDescription>
      </Field>
      <Button
        type="submit"
        className="self-start"
        disabled={acao.isPending || !token}
      >
        {acao.isPending ? "Salvando…" : "Salvar e validar token"}
      </Button>
    </form>
  )
}

function AtivacaoBot({ config, form }: CamposBot) {
  return (
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
        disabled={!config.configurado || form.acao.isPending}
        onCheckedChange={(ativo) => {
          form.salvar({ ativo })
        }}
      />
    </Field>
  )
}

function AcoesBot({ form }: { form: FormularioBot }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="outline"
        disabled={form.acao.isPending}
        onClick={() => {
          form.acao.mutate(
            { tipo: "testar-instancia" },
            {
              onSuccess: () => {
                toast.success("Token válido e bot disponível.")
              },
              onError: falhou,
            }
          )
        }}
      >
        Validar conexão do bot
      </Button>
      <Button
        variant="ghost"
        disabled={form.acao.isPending}
        onClick={() => {
          form.setRemover(true)
        }}
      >
        Remover bot
      </Button>
    </div>
  )
}

function ConfirmacoesBot({ form }: { form: FormularioBot }) {
  return (
    <>
      <ConfirmacaoTelegram
        aberto={!!form.troca}
        pendente={form.acao.isPending}
        foco={form.tokenRef}
        titulo="Substituir o bot da instalação?"
        acao="Substituir bot"
        alterar={(aberto) => {
          if (!aberto) form.setTroca(undefined)
        }}
        confirmar={() => {
          if (form.troca)
            form.salvar({ ...form.troca, confirmar_troca_bot: true })
        }}
      >
        Todos os vínculos serão removidos e os usuários precisarão vincular o
        Telegram novamente. Os relatórios pendentes serão cancelados.
      </ConfirmacaoTelegram>
      <ConfirmacaoTelegram
        aberto={form.remover}
        pendente={form.acao.isPending}
        foco={form.tokenRef}
        titulo="Remover o bot?"
        acao="Remover bot"
        alterar={form.setRemover}
        confirmar={form.removerBot}
      >
        O token e todos os vínculos serão removidos. A sincronização automática
        continuará com a configuração atual.
      </ConfirmacaoTelegram>
    </>
  )
}
