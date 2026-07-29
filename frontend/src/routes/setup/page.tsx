import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { Citrus } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useState } from "react"
import type { ReactNode } from "react"
import { useForm } from "react-hook-form"
import { Navigate, useNavigate } from "react-router"
import { z } from "zod"

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
import { authKeys, useSetupStatus } from "@/lib/api/auth"
import { api } from "@/lib/api/client"

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

type Form = z.infer<typeof schema>
type Iniciado = {
  totp_secret: string
  totp_provisioning_uri: string
  setup_ticket: string
}

export function SetupPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const status = useSetupStatus()
  const [erroServidor, setErroServidor] = useState<string | null>(null)
  const [step, setStep] = useState<"form" | "qr" | "confirm">("form")
  const [iniciado, setIniciado] = useState<Iniciado | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema) })

  // Instância já configurada → não faz sentido mostrar o setup.
  if (status.data?.configured) return <Navigate to="/" replace />

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
        },
        data_nascimento: v.data_nascimento || null,
        salario_mensal: v.salario_mensal
          ? v.salario_mensal.replace(",", ".")
          : null,
      },
    })
    if (error || !data) {
      setErroServidor(
        "Não foi possível continuar. Verifique os dados e tente novamente."
      )
      return
    }
    setIniciado(data)
    setStep("qr")
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Citrus className="size-5" aria-hidden />
          </span>
          <CardTitle className="mt-2 text-lg">
            {step === "form"
              ? "Bem-vindo ao mango"
              : "Verificação em duas etapas"}
          </CardTitle>
          <CardDescription>
            {step === "form"
              ? "Primeira execução: crie a conta do dono da instância e conecte o Open Finance (Pluggy)."
              : step === "qr"
                ? "Escaneie o QR code no seu app autenticador (Google Authenticator, Aegis, etc.)."
                : "Digite o código de 6 dígitos do app para confirmar que o 2FA está funcionando."}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {step === "form" ? (
            <form
              onSubmit={handleSubmit(onSubmit)}
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
              <div className="grid grid-cols-2 gap-3">
                <Field id="senha" label="Senha" error={errors.senha?.message}>
                  <Input
                    id="senha"
                    type="password"
                    autoComplete="new-password"
                    {...register("senha")}
                  />
                </Field>
                <Field
                  id="confirmar"
                  label="Confirmar senha"
                  error={errors.confirmar?.message}
                >
                  <Input
                    id="confirmar"
                    type="password"
                    autoComplete="new-password"
                    {...register("confirmar")}
                  />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
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

              <fieldset className="mt-1 flex flex-col gap-4 rounded-lg border p-3">
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
                <Field
                  id="item_id"
                  label="itemId"
                  error={errors.item_id?.message}
                >
                  <Input
                    id="item_id"
                    autoComplete="off"
                    {...register("item_id")}
                  />
                </Field>
              </fieldset>

              {erroServidor ? (
                <p role="alert" className="text-sm text-destructive">
                  {erroServidor}
                </p>
              ) : null}

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Continuando…" : "Continuar"}
              </Button>
            </form>
          ) : step === "qr" && iniciado ? (
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
              onConcluido={async () => {
                await queryClient.invalidateQueries({
                  queryKey: authKeys.setupStatus,
                })
                await queryClient.invalidateQueries({ queryKey: authKeys.me })
                navigate("/", { replace: true })
              }}
            />
          ) : null}
        </CardContent>
      </Card>
    </main>
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
