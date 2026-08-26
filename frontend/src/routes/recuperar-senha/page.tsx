import { zodResolver } from "@hookform/resolvers/zod"
import { KeyRound } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link } from "react-router"
import { z } from "zod"

import { AuthShell } from "@/components/auth/auth-shell"
import { SenhaInput } from "@/components/auth/senha-input"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useRecuperarSenha } from "@/lib/api/auth"

const schema = z
  .object({
    email: z.string().refine((v) => v.includes("@"), "E-mail inválido"),
    codigo_totp: z.string().min(6, "Código de 6 dígitos"),
    nova_senha: z.string().min(8, "Mínimo de 8 caracteres"),
    confirmar: z.string(),
  })
  .refine((d) => d.nova_senha === d.confirmar, {
    path: ["confirmar"],
    message: "As senhas não conferem",
  })

type Form = z.infer<typeof schema>

/** Recuperação de senha (§5.2, #15): sem e-mail, o código do autenticador é a prova de posse da
 *  conta — só funciona pra quem tem 2FA configurado. Pública, fora do `RequireAuth`. */
export function RecuperarSenhaPage() {
  const recuperar = useRecuperarSenha()
  const [concluido, setConcluido] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema) })

  async function onSubmit(v: Form) {
    setErro(null)
    try {
      await recuperar.mutateAsync({
        email: v.email,
        codigo_totp: v.codigo_totp,
        nova_senha: v.nova_senha,
      })
      setConcluido(true)
    } catch {
      setErro(
        "Não foi possível recuperar a senha. Confira o e-mail e o código."
      )
    }
  }

  return (
    <AuthShell
      cena="scared"
      icone={KeyRound}
      titulo="Recuperar senha"
      descricao="Só é possível recuperar a senha se você tiver o 2FA configurado — o código do autenticador é a prova de que a conta é sua."
    >
      {concluido ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Senha alterada. Todas as sessões ativas foram encerradas — entre
            novamente com a nova senha.
          </p>
          <Button asChild className="w-full">
            <Link to="/login">Ir para o login</Link>
          </Button>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
          noValidate
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">E-mail</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              {...register("email")}
            />
            {errors.email ? (
              <p className="text-xs text-destructive">{errors.email.message}</p>
            ) : null}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="codigo_totp">Código (2FA)</Label>
            <Input
              id="codigo_totp"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              {...register("codigo_totp")}
            />
            {errors.codigo_totp ? (
              <p className="text-xs text-destructive">
                {errors.codigo_totp.message}
              </p>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="nova_senha">Nova senha</Label>
              <SenhaInput
                id="nova_senha"
                placeholder="Digite a nova senha"
                autoComplete="new-password"
                aria-invalid={errors.nova_senha ? true : undefined}
                {...register("nova_senha")}
              />
              {errors.nova_senha ? (
                <p className="text-xs text-destructive">
                  {errors.nova_senha.message}
                </p>
              ) : null}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirmar">Confirmar</Label>
              <SenhaInput
                id="confirmar"
                placeholder="Confirme a nova senha"
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
          </div>

          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Recuperando…" : "Recuperar senha"}
          </Button>
          <Link
            to="/login"
            className="text-center text-xs text-muted-foreground hover:text-primary"
          >
            Voltar para o login
          </Link>
        </form>
      )}
    </AuthShell>
  )
}
