import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { Citrus } from "lucide-react"
import { useState } from "react"
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
import { authKeys, useMe } from "@/lib/api/auth"
import { api } from "@/lib/api/client"

const schema = z.object({
  email: z.string().refine((v) => v.includes("@"), "E-mail inválido"),
  senha: z.string().min(1, "Informe a senha"),
  codigo_totp: z.string().min(6, "Código de 6 dígitos"),
})

type Form = z.infer<typeof schema>

export function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const me = useMe()
  const [erro, setErro] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema) })

  // Já autenticado → volta para a página inicial em vez de mostrar o login.
  if (me.data) return <Navigate to="/" replace />

  async function onSubmit(v: Form) {
    setErro(null)
    const { error } = await api.POST("/api/auth/login", { body: v })
    if (error) {
      setErro("Credenciais inválidas.")
      return
    }
    await queryClient.invalidateQueries({ queryKey: authKeys.me })
    navigate("/", { replace: true })
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Citrus className="size-5" aria-hidden />
          </span>
          <CardTitle className="mt-2 text-lg">Entrar</CardTitle>
          <CardDescription>
            Acesse com sua senha e o código do autenticador.
          </CardDescription>
        </CardHeader>
        <CardContent>
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
                <p className="text-xs text-destructive">
                  {errors.email.message}
                </p>
              ) : null}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="senha">Senha</Label>
              <Input
                id="senha"
                type="password"
                autoComplete="current-password"
                {...register("senha")}
              />
              {errors.senha ? (
                <p className="text-xs text-destructive">
                  {errors.senha.message}
                </p>
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

            {erro ? (
              <p role="alert" className="text-sm text-destructive">
                {erro}
              </p>
            ) : null}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Entrando…" : "Entrar"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
