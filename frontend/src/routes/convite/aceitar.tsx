import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { Lock, ShieldCheck } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { useNavigate, useParams } from "react-router"
import { z } from "zod"

import { AuthShell } from "@/components/auth/auth-shell"
import { SenhaInput } from "@/components/auth/senha-input"
import { TotpOptIn } from "@/components/auth/totp-opt-in"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { authKeys } from "@/lib/api/auth"
import {
  useConfirmarConvite,
  useConviteStatus,
  useIniciarConvite,
  type IniciarConviteResponse,
} from "@/lib/api/convites"

const schema = z
  .object({
    senha: z.string().min(8, "Mínimo de 8 caracteres"),
    confirmar: z.string(),
  })
  .refine((d) => d.senha === d.confirmar, {
    path: ["confirmar"],
    message: "As senhas não conferem",
  })

type Form = z.infer<typeof schema>

/** Aceitar convite de "só divisão" (§4.11, §3) — mesmo desenho de 2 passos do first-run setup
 *  (`routes/setup/page.tsx`), mas o usuário já existe (placeholder) desde o convite: só falta
 *  senha + TOTP. Pública, fora do `RequireAuth` (ver router.tsx). */
export function AceitarConvitePage() {
  const { token = "" } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const status = useConviteStatus(token)
  const iniciar = useIniciarConvite(token)
  const confirmar = useConfirmarConvite()
  const [step, setStep] = useState<"form" | "qr" | "confirm">("form")
  const [iniciado, setIniciado] = useState<IniciarConviteResponse | null>(null)
  const [erroServidor, setErroServidor] = useState<string | null>(null)
  const [ativarTotp, setAtivarTotp] = useState(true)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema) })

  async function finalizar() {
    await queryClient.invalidateQueries({ queryKey: authKeys.me })
    navigate("/", { replace: true })
  }

  async function onSubmit(v: Form) {
    setErroServidor(null)
    try {
      const dados = await iniciar.mutateAsync({
        senha: v.senha,
        ativar_totp: ativarTotp,
      })
      if (!dados.totp_secret) {
        // Pulou o 2FA — conclui direto, sem passar pelo QR nem pedir código.
        await confirmar.mutateAsync({ ticket: dados.ticket })
        await finalizar()
        return
      }
      setIniciado(dados)
      setStep("qr")
    } catch (err) {
      setErroServidor(
        err instanceof Error ? err.message : "Não foi possível continuar."
      )
    }
  }

  const titulo =
    step === "form" ? (
      <>
        Bem-vindo ao <span className="text-primary">mango</span>!
      </>
    ) : (
      "Verificação em duas etapas"
    )

  const conviteUtilizavel =
    !status.isLoading &&
    status.data &&
    !status.data.usado &&
    !status.data.expirado

  return (
    <AuthShell
      cena="money-v2"
      icone={step === "form" ? Lock : ShieldCheck}
      titulo={titulo}
      descricao={
        status.isLoading
          ? "Carregando convite…"
          : status.isError || !status.data
            ? "Convite não encontrado."
            : status.data.usado
              ? "Este convite já foi utilizado — faça login normalmente."
              : status.data.expirado
                ? "Este convite expirou. Peça a quem te convidou para gerar um novo link."
                : step === "form"
                  ? `Olá, ${status.data.nome}! 👋 Defina sua senha para entrar nesta instância.`
                  : step === "qr"
                    ? "Escaneie o QR code no seu app autenticador (Google Authenticator, Aegis, etc.)."
                    : "Digite o código de 6 dígitos do app para confirmar que o 2FA está funcionando."
      }
    >
      {!conviteUtilizavel ? null : step === "form" ? (
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
          noValidate
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="senha">Senha</Label>
            <SenhaInput
              id="senha"
              placeholder="Digite sua senha"
              autoComplete="new-password"
              aria-invalid={errors.senha ? true : undefined}
              {...register("senha")}
            />
            {errors.senha ? (
              <p className="text-xs text-destructive">{errors.senha.message}</p>
            ) : null}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirmar">Confirmar senha</Label>
            <SenhaInput
              id="confirmar"
              placeholder="Confirme sua senha"
              autoComplete="new-password"
              aria-invalid={errors.confirmar ? true : undefined}
              {...register("confirmar")}
            />
            {errors.confirmar ? (
              <p className="text-xs text-destructive">
                {errors.confirmar.message}
              </p>
            ) : null}
          </div>

          <TotpOptIn checked={ativarTotp} onCheckedChange={setAtivarTotp} />

          {erroServidor ? (
            <p role="alert" className="text-sm text-destructive">
              {erroServidor}
            </p>
          ) : null}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Continuando…" : "Continuar"}
          </Button>
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
          ticket={iniciado.ticket}
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
  const confirmar = useConfirmarConvite()

  async function verificar() {
    setErro(null)
    try {
      await confirmar.mutateAsync({ ticket, codigo_totp: codigo })
      await onConcluido()
    } catch (err) {
      setErro(
        err instanceof Error
          ? err.message
          : "Código incorreto. Confira o app autenticador e tente de novo."
      )
    }
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
          disabled={confirmar.isPending}
        >
          Voltar
        </Button>
        <Button
          className="flex-1"
          onClick={verificar}
          disabled={confirmar.isPending || codigo.length < 6}
        >
          {confirmar.isPending ? "Verificando…" : "Verificar e concluir"}
        </Button>
      </div>
    </div>
  )
}
