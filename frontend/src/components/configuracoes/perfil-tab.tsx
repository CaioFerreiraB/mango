import { useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useAtualizarPerfil,
  usePerfil,
  type Perfil,
  type PerfilUpdate,
} from "@/lib/api/perfil"

export function PerfilTab() {
  const perfil = usePerfil()
  if (perfil.isLoading || !perfil.data)
    return <Skeleton className="h-72 w-full" />
  // Chaveado pelo id: o form inicializa seu estado a partir dos dados já carregados (sem effect).
  return <PerfilForm key={perfil.data.id} perfil={perfil.data} />
}

function PerfilForm({ perfil }: { perfil: Perfil }) {
  const atualizar = useAtualizarPerfil()
  const [form, setForm] = useState({
    nome: perfil.nome,
    email: perfil.email,
    data_nascimento: perfil.data_nascimento ?? "",
    // em reais na UI; convertido para centavos ao salvar
    salario:
      perfil.salario_mensal_centavos != null
        ? String(perfil.salario_mensal_centavos / 100)
        : "",
    formacao: perfil.formacao ?? "",
    ocupacao: perfil.ocupacao ?? "",
  })

  function salvar(e: React.FormEvent) {
    e.preventDefault()
    const patch: PerfilUpdate = {
      nome: form.nome,
      email: form.email,
      data_nascimento: form.data_nascimento || null,
      salario_mensal_centavos: form.salario
        ? Math.round(Number(form.salario) * 100)
        : null,
      formacao: form.formacao || null,
      ocupacao: form.ocupacao || null,
    }
    atualizar.mutate(patch, {
      onSuccess: () => toast.success("Perfil atualizado."),
      onError: (err) => toast.error(err.message),
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Dados do cadastro</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={salvar}>
          <Campo
            label="Nome"
            id="nome"
            value={form.nome}
            onChange={(v) => setForm({ ...form, nome: v })}
            required
          />
          <Campo
            label="E-mail"
            id="email"
            type="email"
            value={form.email}
            onChange={(v) => setForm({ ...form, email: v })}
            required
          />
          <Campo
            label="Data de nascimento"
            id="nasc"
            type="date"
            value={form.data_nascimento}
            onChange={(v) => setForm({ ...form, data_nascimento: v })}
          />
          <Campo
            label="Salário mensal (R$)"
            id="salario"
            type="number"
            value={form.salario}
            onChange={(v) => setForm({ ...form, salario: v })}
          />
          <Campo
            label="Formação"
            id="formacao"
            value={form.formacao}
            onChange={(v) => setForm({ ...form, formacao: v })}
          />
          <Campo
            label="Ocupação"
            id="ocupacao"
            value={form.ocupacao}
            onChange={(v) => setForm({ ...form, ocupacao: v })}
          />
          <div className="flex items-center justify-between sm:col-span-2">
            <Button type="submit" disabled={atualizar.isPending}>
              Salvar
            </Button>
            <Link
              to="/fontes-de-renda"
              className="text-sm text-muted-foreground hover:text-primary"
            >
              Fontes de renda →
            </Link>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function Campo({
  label,
  id,
  value,
  onChange,
  type = "text",
  required,
}: {
  label: string
  id: string
  value: string
  onChange: (v: string) => void
  type?: string
  required?: boolean
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
      />
    </div>
  )
}
