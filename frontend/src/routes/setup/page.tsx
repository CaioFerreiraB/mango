import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { Landmark, Loader2, Lock, ShieldCheck } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useState } from "react"
import type { ReactNode } from "react"
import { useForm } from "react-hook-form"
import { Navigate, useNavigate } from "react-router"
import { z } from "zod"

import { AuthShell } from "@/components/auth/auth-shell"
import { SenhaInput } from "@/components/auth/senha-input"
import { TotpOptIn } from "@/components/auth/totp-opt-in"
import { InstituicaoSelect } from "@/components/contas/instituicao-select"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { authKeys, useSetupStatus } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { Connector } from "@/lib/api/instituicoes"

const schema = z
  .object({
    nome: z.string().min(1, "Informe seu nome"),
    email: z.string().refine((v) => v.includes("@"), "E-mail inválido"),
    senha: z.string().min(8, "Mínimo de 8 caracteres"),
    confirmar: z.string(),
    data_nascimento: z.string().optional(),
    salario_mensal: z.string().optional(),
    client_id: z.string().min(1, "Obrigatório"),
    client_secret: z.string().min(1, "Obrigatório"),
    item_id: z.string().min(1, "Obrigatório"),
  })
  .refine((d) => d.senha === d.confirmar, {
    path: ["confirmar"],
    message: "As senhas não conferem",
  })

/** Mensagem do backend (`{detail: "…"}` dos erros de domínio). O 422 do pydantic traz uma lista
 *  em `detail` — aí não serve de texto para o usuário e cai no fallback de quem chama. */
function detalhe(erro: unknown): string | null {
  const d = (erro as { detail?: unknown } | undefined)?.detail
  return typeof d === "string" ? d : null
}

type Form = z.infer<typeof schema>
/** Campos do primeiro passo — validados antes de liberar o passo da conexão. */
const CAMPOS_CONTA = [
  "nome",
  "email",
  "senha",
  "confirmar",
  "data_nascimento",
  "salario_mensal",
] as const
type Iniciado = {
  totp_secret: string | null
  totp_provisioning_uri: string | null
  setup_ticket: string
}

export function SetupPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const status = useSetupStatus()
  const [erroServidor, setErroServidor] = useState<string | null>(null)
  const [step, setStep] = useState<
    "conta" | "pluggy" | "qr" | "confirm" | "sync"
  >("conta")
  const [iniciado, setIniciado] = useState<Iniciado | null>(null)
  const [ativarTotp, setAtivarTotp] = useState(true)
  const [connector, setConnector] = useState<Connector | null>(null)

  const {
    register,
    handleSubmit,
    trigger,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema) })

  // Instância já configurada → não faz sentido mostrar o setup.
  if (status.data?.configured) return <Navigate to="/" replace />

  async function finalizar() {
    // Já logado pelo `confirmar`: puxa as contas da conexão recém-criada para a home não nascer
    // vazia. Falha de sync não bloqueia — dá para tentar de novo em Configurações → Conexões.
    setStep("sync")
    await api.POST("/api/sync").catch(() => undefined)
    await queryClient.invalidateQueries({ queryKey: authKeys.setupStatus })
    await queryClient.invalidateQueries({ queryKey: authKeys.me })
    navigate("/", { replace: true })
  }

  async function avancarParaPluggy() {
    setErroServidor(null)
    // Só o passo 1: nada é enviado ainda. Os valores sobrevivem à troca de passo (o RHF mantém
    // campos desmontados), então voltar e avançar de novo não perde o que foi digitado.
    if (await trigger(CAMPOS_CONTA)) setStep("pluggy")
  }

  async function onSubmit(v: Form) {
    setErroServidor(null)
    const { data, error } = await api.POST("/api/setup", {
      body: {
        nome: v.nome,
        email: v.email,
        senha: v.senha,
        pluggy: {
          client_id: v.client_id,
          client_secret: v.client_secret,
          item_id: v.item_id,
          instituicao: connector,
        },
        data_nascimento: v.data_nascimento || null,
        salario_mensal: v.salario_mensal
          ? v.salario_mensal.replace(",", ".")
          : null,
        ativar_totp: ativarTotp,
      },
    })
    if (error || !data) {
      // O backend valida a conexão do Pluggy ao vivo e diz o que está errado (credencial ou
      // itemId) — mostramos essa mensagem; a genérica cobre 422 de schema e falha de rede.
      setErroServidor(
        detalhe(error) ??
          "Não foi possível continuar. Verifique os dados e tente novamente."
      )
      return
    }
    if (!data.totp_secret) {
      // Pulou o 2FA — conclui direto, sem passar pelo QR nem pedir código.
      const { error: erroConfirmar } = await api.POST("/api/setup/confirmar", {
        body: { setup_ticket: data.setup_ticket },
      })
      if (erroConfirmar) {
        setErroServidor("Não foi possível concluir o cadastro. Tente novamente.")
        return
      }
      await finalizar()
      return
    }
    setIniciado(data)
    setStep("qr")
  }

  return (
    <AuthShell
      cena="money-v2"
      cenaDesktop="money"
      icone={
        step === "conta"
          ? Lock
          : step === "pluggy"
            ? Landmark
            : step === "sync"
              ? Loader2
              : ShieldCheck
      }
      titulo={
        step === "conta" ? (
          <>
            Bem-vindo ao <span className="text-primary">mango</span>!
          </>
        ) : step === "pluggy" ? (
          "Conecte o Open Finance"
        ) : step === "sync" ? (
          "Conectando ao seu banco"
        ) : (
          "Verificação em duas etapas"
        )
      }
      descricao={
        step === "conta"
          ? "Primeira execução: comece criando a conta do dono da instância."
          : step === "pluggy"
            ? "Agora as credenciais do seu app no Pluggy e a primeira conexão bancária."
            : step === "qr"
              ? "Escaneie o QR code no seu app autenticador (Google Authenticator, Aegis, etc.)."
              : step === "sync"
                ? "Importando as contas e as transações da conexão. Isso leva alguns instantes."
                : "Digite o código de 6 dígitos do app para confirmar que o 2FA está funcionando."
      }
    >
      {step === "sync" ? (
        <div
          role="status"
          className="flex items-center gap-3 text-sm text-muted-foreground"
        >
          <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
          Sincronizando suas contas…
        </div>
      ) : step === "conta" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            avancarParaPluggy()
          }}
          className="flex flex-col gap-4"
          noValidate
        >
          <Field id="nome" label="Nome" error={errors.nome?.message}>
            <Input id="nome" autoComplete="name" {...register("nome")} />
          </Field>
          <Field id="email" label="E-mail" error={errors.email?.message}>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              {...register("email")}
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="senha" label="Senha" error={errors.senha?.message}>
              <SenhaInput
                id="senha"
                placeholder="Digite sua senha"
                autoComplete="new-password"
                aria-invalid={errors.senha ? true : undefined}
                {...register("senha")}
              />
            </Field>
            <Field
              id="confirmar"
              label="Confirmar senha"
              error={errors.confirmar?.message}
            >
              <SenhaInput
                id="confirmar"
                placeholder="Confirme sua senha"
                autoComplete="new-password"
                aria-invalid={errors.confirmar ? true : undefined}
                {...register("confirmar")}
              />
            </Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="data_nascimento" label="Nascimento (opcional)">
              <Input
                id="data_nascimento"
                type="date"
                {...register("data_nascimento")}
              />
            </Field>
            <Field id="salario_mensal" label="Salário mensal (opcional)">
              <Input
                id="salario_mensal"
                inputMode="decimal"
                placeholder="R$ 0,00"
                {...register("salario_mensal")}
              />
            </Field>
          </div>

          <TotpOptIn checked={ativarTotp} onCheckedChange={setAtivarTotp} />

          <Button type="submit" className="w-full">
            Continuar
          </Button>
        </form>
      ) : step === "pluggy" ? (
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
          noValidate
        >
          <fieldset className="flex flex-col gap-4 rounded-lg border p-3">
            <legend className="px-1 text-xs font-medium text-muted-foreground">
              Conexão Pluggy (Open Finance)
            </legend>
            <Field
              id="client_id"
              label="clientId"
              error={errors.client_id?.message}
            >
              <Input
                id="client_id"
                autoComplete="off"
                {...register("client_id")}
              />
            </Field>
            <Field
              id="client_secret"
              label="clientSecret"
              error={errors.client_secret?.message}
            >
              <Input
                id="client_secret"
                type="password"
                autoComplete="off"
                {...register("client_secret")}
              />
            </Field>
            <Field id="item_id" label="itemId" error={errors.item_id?.message}>
              <Input
                id="item_id"
                autoComplete="off"
                {...register("item_id")}
              />
            </Field>
            <div className="flex flex-col gap-1.5">
              <Label>Instituição (opcional)</Label>
              <p className="text-xs text-muted-foreground">
                Esta primeira conexão vincula uma instituição financeira, e o
                vínculo vale para todas as contas dela. Sem escolha, usamos o
                nome detectado pelo Pluggy. Outras conexões podem ser
                adicionadas depois em Configurações → Conexões.
              </p>
              {/* Contorno próprio: aqui o seletor vive solto no formulário, e não dentro de um
                  dialog como em Configurações → Conexões. */}
              <div className="rounded-md border">
                <InstituicaoSelect
                  fonte="setup"
                  value={connector?.pluggy_connector_id ?? null}
                  onChange={setConnector}
                />
              </div>
            </div>
          </fieldset>

          {erroServidor ? (
            <p role="alert" className="text-sm text-destructive">
              {erroServidor}
            </p>
          ) : null}

          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              onClick={() => setStep("conta")}
              disabled={isSubmitting}
            >
              Voltar
            </Button>
            <Button type="submit" className="flex-1" disabled={isSubmitting}>
              {isSubmitting ? "Conectando…" : "Continuar"}
            </Button>
          </div>
        </form>
      ) : step === "qr" && iniciado?.totp_provisioning_uri ? (
        <div className="flex flex-col items-center gap-4">
          <div className="rounded-lg bg-white p-3">
            <QRCodeSVG value={iniciado.totp_provisioning_uri} size={180} />
          </div>
          <div className="w-full">
            <Label>Ou insira a chave manualmente</Label>
            <code className="mt-1 block rounded-md bg-muted px-2 py-1.5 text-xs break-all">
              {iniciado.totp_secret}
            </code>
          </div>
          <Button className="w-full" onClick={() => setStep("confirm")}>
            Já escaneei
          </Button>
        </div>
      ) : iniciado ? (
        <ConfirmStep
          ticket={iniciado.setup_ticket}
          onVoltar={() => setStep("qr")}
          onConcluido={finalizar}
        />
      ) : null}
    </AuthShell>
  )
}

function ConfirmStep({
  ticket,
  onVoltar,
  onConcluido,
}: {
  ticket: string
  onVoltar: () => void
  onConcluido: () => void | Promise<void>
}) {
  const [codigo, setCodigo] = useState("")
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function verificar() {
    setErro(null)
    setEnviando(true)
    const { error } = await api.POST("/api/setup/confirmar", {
      body: { setup_ticket: ticket, codigo_totp: codigo },
    })
    setEnviando(false)
    if (error) {
      setErro("Código incorreto. Confira o app autenticador e tente de novo.")
      return
    }
    await onConcluido()
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="codigo_totp">Código do autenticador</Label>
        <Input
          id="codigo_totp"
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="000000"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && codigo.length >= 6) verificar()
          }}
        />
      </div>

      {erro ? (
        <p role="alert" className="text-sm text-destructive">
          {erro}
        </p>
      ) : null}

      <div className="flex gap-2">
        <Button
          variant="outline"
          className="flex-1"
          onClick={onVoltar}
          disabled={enviando}
        >
          Voltar
        </Button>
        <Button
          className="flex-1"
          onClick={verificar}
          disabled={enviando || codigo.length < 6}
        >
          {enviando ? "Verificando…" : "Verificar e concluir"}
        </Button>
      </div>
    </div>
  )
}

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string
  label: string
  error?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}
