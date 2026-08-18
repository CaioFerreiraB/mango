import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { LogIn, ShieldCheck } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, Navigate, useNavigate } from "react-router"
import { z } from "zod"

import { AuthShell } from "@/components/auth/auth-shell"
import { SenhaInput } from "@/components/auth/senha-input"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { authKeys, useLogin, useMe } from "@/lib/api/auth"

const schemaCredenciais = z.object({
  email: z.string().refine((v) => v.includes("@"), "E-mail inválido"),
  senha: z.string().min(1, "Informe a senha"),
})
type CredenciaisForm = z.infer<typeof schemaCredenciais>

const schemaTotp = z.object({
  codigo_totp: z.string().min(6, "Código de 6 dígitos"),
})
type TotpForm = z.infer<typeof schemaTotp>

/** Login em 2 fases (§5.2, #15): credenciais primeiro; o código só é pedido se o backend
 *  responder `totp_necessario` (a conta tem 2FA habilitado para login) — sem 2FA configurado,
 *  ou com a exigência desligada em Configurações, a senha certa já basta. */
export function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const me = useMe()
  const login = useLogin()
  const [fase, setFase] = useState<"credenciais" | "totp">("credenciais")
  const [credenciais, setCredenciais] = useState<CredenciaisForm | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const formCredenciais = useForm<CredenciaisForm>({
    resolver: zodResolver(schemaCredenciais),
  })
  const formTotp = useForm<TotpForm>({ resolver: zodResolver(schemaTotp) })

  // Já autenticado → volta para a página inicial em vez de mostrar o login.
  if (me.data) return <Navigate to="/" replace />

  async function concluir(v: { email: string; senha: string; codigo_totp?: string }) {
    setErro(null)
    try {
      const resp = await login.mutateAsync(v)
      if (resp.totp_necessario) {
        setCredenciais({ email: v.email, senha: v.senha })
        setFase("totp")
        return
      }
      await queryClient.invalidateQueries({ queryKey: authKeys.me })
      navigate("/", { replace: true })
    } catch {
      setErro("Credenciais inválidas.")
    }
  }

  return (
    <AuthShell
      cena="hang-loose"
      icone={fase === "credenciais" ? LogIn : ShieldCheck}
      titulo={
        fase === "credenciais" ? (
          <>
            Entrar no <span className="text-primary">mango</span>
          </>
        ) : (
          "Verificação em duas etapas"
        )
      }
      descricao={
        fase === "credenciais"
          ? "Acesse com seu e-mail e senha."
          : "Digite o código do seu app autenticador."
      }
    >
      {fase === "credenciais" ? (
        <form
          onSubmit={formCredenciais.handleSubmit((v) => concluir(v))}
          className="flex flex-col gap-4"
          noValidate
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">E-mail</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              {...formCredenciais.register("email")}
            />
            {formCredenciais.formState.errors.email ? (
              <p className="text-xs text-destructive">
                {formCredenciais.formState.errors.email.message}
              </p>
            ) : null}
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="senha">Senha</Label>
              <Link
                to="/recuperar-senha"
                className="text-xs text-muted-foreground hover:text-primary"
              >
                Esqueci minha senha
              </Link>
            </div>
            <SenhaInput
              id="senha"
              placeholder="Digite sua senha"
              autoComplete="current-password"
              aria-invalid={
                formCredenciais.formState.errors.senha ? true : undefined
              }
              {...formCredenciais.register("senha")}
            />
            {formCredenciais.formState.errors.senha ? (
              <p className="text-xs text-destructive">
                {formCredenciais.formState.errors.senha.message}
              </p>
            ) : null}
          </div>

          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}

          <Button
            type="submit"
            className="w-full"
            disabled={formCredenciais.formState.isSubmitting}
          >
            {formCredenciais.formState.isSubmitting ? "Entrando…" : "Entrar"}
          </Button>
        </form>
      ) : (
        <form
          onSubmit={formTotp.handleSubmit((v) =>
            concluir({ ...credenciais!, codigo_totp: v.codigo_totp })
          )}
          className="flex flex-col gap-4"
          noValidate
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="codigo_totp">Código (2FA)</Label>
            <Input
              id="codigo_totp"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              autoFocus
              {...formTotp.register("codigo_totp")}
            />
            {formTotp.formState.errors.codigo_totp ? (
              <p className="text-xs text-destructive">
                {formTotp.formState.errors.codigo_totp.message}
              </p>
            ) : null}
          </div>

          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}

          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              onClick={() => {
                setErro(null)
                setFase("credenciais")
              }}
              disabled={formTotp.formState.isSubmitting}
            >
              Voltar
            </Button>
            <Button
              type="submit"
              className="flex-1"
              disabled={formTotp.formState.isSubmitting}
            >
              {formTotp.formState.isSubmitting ? "Entrando…" : "Entrar"}
            </Button>
          </div>
        </form>
      )}
    </AuthShell>
  )
}
