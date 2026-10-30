import { useMutation, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useMe, useSetupStatus } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import type { components } from "@/lib/api/schema"

type Config = components["schemas"]["ConfigIaRead"]
function falhou(e: Error) {
  toast.error(e.message)
}

export function IaTab() {
  const me = useMe()
  const modo = useSetupStatus()
  const administra =
    modo.data?.app_mode === "local" || me.data?.is_admin === true
  const instancia = useQuery({
    queryKey: ["ia", "instancia"],
    enabled: administra,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/ia/instancia")
      if (error || !data)
        throw new Error(
          mensagemErro(error, "Falha ao carregar a configuração.")
        )
      return data
    },
  })
  const pref = useQuery({
    queryKey: ["ia", "preferencias"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/ia/preferencias")
      if (error || !data)
        throw new Error(mensagemErro(error, "Falha ao carregar a preferência."))
      return data
    },
  })
  const mudar = useMutation({
    mutationFn: async (ativa: boolean) => {
      const { error } = await api.PUT("/api/ia/preferencias", {
        body: { ativa },
      })
      if (error) throw new Error(mensagemErro(error, "Falha ao salvar."))
    },
    onSuccess: () => {
      void pref.refetch()
    },
    onError: falhou,
  })
  return (
    <div className="max-w-2xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Conversar pelo Telegram</CardTitle>
          <CardDescription>
            Suas mensagens e os dados consultados serão enviados ao provedor{" "}
            {pref.data?.provedor === "axon"
              ? "Axon"
              : "configurado pela instalação"}
            . O Mango guarda o histórico cifrado por sete dias.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {pref.isError ? (
            <p role="alert">{pref.error.message}</p>
          ) : (
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="ia-pessoal">Ativar conversa com meus dados</Label>
              <Switch
                id="ia-pessoal"
                checked={pref.data?.ativa ?? false}
                disabled={
                  mudar.isPending ||
                  !pref.data ||
                  (!pref.data.disponivel && !pref.data.ativa)
                }
                onCheckedChange={(v) => mudar.mutate(v)}
              />
            </div>
          )}
          {pref.data && !pref.data.disponivel ? (
            <p className="mt-3 text-sm text-muted-foreground">
              A IA está desativada nesta instalação. Os comandos do bot
              continuam disponíveis.
            </p>
          ) : null}
        </CardContent>
      </Card>
      {administra ? (
        instancia.data ? (
          <IaForm
            key={JSON.stringify(instancia.data)}
            config={instancia.data}
            recarregar={() => {
              void instancia.refetch()
              void pref.refetch()
            }}
          />
        ) : (
          <p role="status">
            {instancia.error?.message ?? "Carregando configuração…"}
          </p>
        )
      ) : null}
    </div>
  )
}

function IaForm({
  config,
  recarregar,
}: {
  config: Config
  recarregar: () => void
}) {
  const status = useSetupStatus()
  const [tipo, setTipo] = useState<"axon" | "openai_compatible">(
    config.provedor === "axon" ? "axon" : "openai_compatible"
  )
  const [endpoint, setEndpoint] = useState(config.endpoint ?? "")
  const [chave, setChave] = useState("")
  const [modelo, setModelo] = useState(config.modelo ?? "")
  const [ativa, setAtiva] = useState(config.ativa)
  const [usuario, setUsuario] = useState(config.limite_usuario)
  const [instancia, setInstancia] = useState(config.limite_instancia)
  const alterada =
    tipo !== config.provedor ||
    endpoint !== config.endpoint ||
    !!chave ||
    (tipo !== "axon" && modelo !== config.modelo)
  const salvar = useMutation({
    mutationFn: async () => {
      const comum = { tipo, endpoint, ...(chave ? { chave } : {}) }
      const { error } = await api.PUT("/api/ia/instancia", {
        body: {
          ativa: alterada ? false : ativa,
          provedor:
            tipo === "axon" ? { ...comum, tipo } : { ...comum, tipo, modelo },
          limite_usuario: usuario,
          limite_instancia: instancia,
        },
      })
      if (error) throw new Error(mensagemErro(error, "Falha ao salvar a IA."))
    },
    onSuccess: () => {
      setChave("")
      recarregar()
      toast.success("Configuração salva.")
    },
    onError: falhou,
  })
  const testar = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/ia/instancia/testar")
      if (error) throw new Error(mensagemErro(error, "Falha ao testar a IA."))
    },
    onSuccess: () => {
      recarregar()
      toast.success("Conexão validada. Você já pode ativar a IA.")
    },
    onError: (e) => {
      recarregar()
      falhou(e)
    },
  })
  const ocupado = salvar.isPending || testar.isPending
  return (
    <Card>
      <CardHeader>
        <CardTitle>IA da instalação</CardTitle>
        <CardDescription>
          Salve as credenciais, teste a conexão e depois ative. Trocar a conexão
          desativa a IA até um novo teste.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            salvar.mutate()
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="ia-provedor">Provedor</Label>
            <Select
              value={tipo}
              onValueChange={(v) => {
                setTipo(v as typeof tipo)
                setChave("")
                setModelo("")
                setAtiva(false)
              }}
            >
              <SelectTrigger id="ia-provedor">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="openai_compatible">
                  API OpenAI-compatible
                </SelectItem>
                {status.data?.app_mode === "self_hosted" ? (
                  <SelectItem value="axon">Axon</SelectItem>
                ) : null}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="ia-endpoint">Endpoint HTTPS</Label>
            <Input
              id="ia-endpoint"
              type="url"
              required
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder={
                tipo === "axon"
                  ? "https://axon.exemplo.com/private/v1"
                  : "https://api.exemplo.com/v1"
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ia-chave">Chave de API</Label>
            <Input
              id="ia-chave"
              type="password"
              autoComplete="new-password"
              value={chave}
              onChange={(e) => setChave(e.target.value)}
              placeholder={
                config.configurada
                  ? "Deixe vazio para manter a chave"
                  : "Cole sua chave"
              }
            />
          </div>
          {tipo === "openai_compatible" ? (
            <div className="space-y-2">
              <Label htmlFor="ia-modelo">Modelo</Label>
              <Input
                id="ia-modelo"
                value={modelo}
                required
                onChange={(e) => setModelo(e.target.value)}
              />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              O Assistant será descoberto automaticamente. A chave precisa
              acessar exatamente um Assistant com delegação para o MCP desta
              instalação.
            </p>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="ia-limite-pessoa">Mensagens por pessoa/dia</Label>
              <Input
                id="ia-limite-pessoa"
                type="number"
                min={1}
                max={10000}
                required
                value={usuario}
                onChange={(e) => setUsuario(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ia-limite-total">
                Mensagens por instalação/dia
              </Label>
              <Input
                id="ia-limite-total"
                type="number"
                min={1}
                max={100000}
                required
                value={instancia}
                onChange={(e) => setInstancia(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="ia-ativa">IA ativa</Label>
            <Switch
              id="ia-ativa"
              checked={ativa && !alterada}
              disabled={!config.validada || alterada || ocupado}
              onCheckedChange={setAtiva}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={ocupado}>
              Salvar configuração
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={ocupado || alterada || !config.configurada}
              onClick={() => testar.mutate()}
            >
              {testar.isPending ? "Testando…" : "Testar conexão"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

export function MiniappConfigForm() {
  const config = useQuery({
    queryKey: ["telegram", "miniapp"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/telegram/miniapp/config")
      if (error || !data)
        throw new Error(mensagemErro(error, "Falha ao carregar o miniapp."))
      return data
    },
  })
  return config.data ? (
    <MiniappForm
      key={JSON.stringify(config.data)}
      config={config.data}
      recarregar={() => void config.refetch()}
    />
  ) : (
    <p role="status">{config.error?.message ?? "Carregando miniapp…"}</p>
  )
}
function MiniappForm({
  config,
  recarregar,
}: {
  config: components["schemas"]["MiniappConfig"]
  recarregar: () => void
}) {
  const [url, setUrl] = useState(config.url ?? window.location.origin)
  const [ativo, setAtivo] = useState(config.ativo)
  const salvar = useMutation({
    mutationFn: async () => {
      const { error } = await api.PUT("/api/telegram/miniapp/config", {
        body: { ativo, url },
      })
      if (error)
        throw new Error(mensagemErro(error, "Falha ao configurar o miniapp."))
    },
    onSuccess: () => {
      recarregar()
      toast.success("Miniapp configurado.")
    },
    onError: falhou,
  })
  return (
    <Card>
      <CardHeader>
        <CardTitle>Miniapp do Telegram</CardTitle>
        <CardDescription>
          Confirme o endereço público HTTPS desta instalação. O menu do bot
          abrirá a revisão e as divisões.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            salvar.mutate()
          }}
        >
          <Label htmlFor="miniapp-url">Endereço do Mango</Label>
          <Input
            id="miniapp-url"
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="miniapp-ativo">Habilitar miniapp</Label>
            <Switch
              id="miniapp-ativo"
              checked={ativo}
              onCheckedChange={setAtivo}
            />
          </div>
          <Button disabled={salvar.isPending}>Salvar e configurar menu</Button>
        </form>
      </CardContent>
    </Card>
  )
}
