import { Check, Copy, Eye, EyeOff, RefreshCw } from "lucide-react"
import { type Dispatch, useState } from "react"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useSetupStatus } from "@/lib/api/auth"
import {
  type AcessoMcp,
  revelarTokenMcp,
  useAcessoMcp,
  useAtualizarAcessoMcp,
  useTrocarTokenMcp,
} from "@/lib/api/mcp"
import { formatDateTime } from "@/lib/format"

const TOKEN_OCULTO = "••••••••••••••••••••••••"

/** Aba "MCP" em Configurações (docs/mcp.md): liga/desliga o acesso de agentes (Claude Code,
 * Codex, Open WebUI, bots…), escolhe a permissão e mostra/copia/troca o token. */
export function McpTab() {
  const status = useSetupStatus()
  const url = `${window.location.origin}/mcp`

  if (status.isLoading) return <Skeleton className="h-40 w-full" />
  if (status.data?.app_mode === "local") return <McpLocal url={url} />
  return <McpSelfHosted url={url} />
}

/** Modo local: sem login, sem token — o MCP só atende esta máquina (localhost). */
function McpLocal({ url }: { url: string }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Acesso por agentes (MCP)</CardTitle>
          <CardDescription>
            No modo local o MCP não usa token: ele aceita só conexões desta
            máquina, como o resto do app. Aponte o agente para o endereço
            abaixo.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Endereco url={url} />
        </CardContent>
      </Card>
      <Snippets url={url} token={null} />
    </div>
  )
}

function McpSelfHosted({ url }: { url: string }) {
  const acesso = useAcessoMcp()
  // Token em claro só na memória da aba, e só depois de Mostrar/Copiar/Trocar.
  const [token, setToken] = useState<string | null>(null)

  if (acesso.isLoading || !acesso.data)
    return <Skeleton className="h-40 w-full" />
  const a = acesso.data

  async function obterToken(): Promise<string> {
    if (token) return token
    const t = await revelarTokenMcp()
    setToken(t)
    return t
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Acesso por agentes (MCP)</CardTitle>
          <CardDescription>
            Deixa agentes de IA — Claude Code, Codex, Open WebUI, bots de
            Telegram/WhatsApp — consultarem e, se você permitir, alterarem seus
            dados financeiros. Configurações do sistema nunca ficam acessíveis
            por aqui.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <AtivarMcp ativo={a.ativo} />
          {a.configurado ? (
            <>
              <PermissaoMcp escopo={a.escopo} />
              <CampoToken
                acesso={a}
                token={token}
                obterToken={obterToken}
                aoTrocar={setToken}
              />
            </>
          ) : null}
          <Endereco url={url} />
        </CardContent>
      </Card>
      {a.configurado ? <Snippets url={url} token={obterToken} /> : null}
    </div>
  )
}

function AtivarMcp({ ativo }: { ativo: boolean }) {
  const atualizar = useAtualizarAcessoMcp()
  return (
    <label className="flex items-start justify-between gap-4">
      <span className="flex flex-col gap-0.5">
        <span className="text-sm font-medium">Ativar acesso via MCP</span>
        <span className="text-sm text-muted-foreground">
          Desativado, o token deixa de funcionar na hora; ao reativar, o mesmo
          token volta a valer.
        </span>
      </span>
      <Switch
        checked={ativo}
        disabled={atualizar.isPending}
        onCheckedChange={(novo) => {
          atualizar.mutate(
            { ativo: novo },
            {
              onSuccess: () =>
                toast.success(
                  novo ? "Acesso MCP ativado." : "Acesso MCP desativado."
                ),
              onError: (err) => toast.error(err.message),
            }
          )
        }}
      />
    </label>
  )
}

const PERMISSOES = [
  {
    valor: "leitura",
    titulo: "Só leitura",
    descricao: "Consulta transações, contas, faturas, objetivos e saldos.",
  },
  {
    valor: "escrita",
    titulo: "Leitura e escrita",
    descricao:
      "Também revisa e categoriza transações, gerencia assinaturas e cria divisões de contas.",
  },
] as const

function PermissaoMcp({ escopo }: { escopo: AcessoMcp["escopo"] }) {
  const atualizar = useAtualizarAcessoMcp()
  return (
    <div className="space-y-2">
      <Label>Permissão</Label>
      <RadioGroup
        value={escopo}
        onValueChange={(v) => {
          atualizar.mutate(
            { escopo: v as AcessoMcp["escopo"] },
            {
              onSuccess: () => toast.success("Permissão atualizada."),
              onError: (err) => toast.error(err.message),
            }
          )
        }}
        className="gap-2"
      >
        {PERMISSOES.map((p) => (
          <label key={p.valor} className="flex items-start gap-2">
            <RadioGroupItem value={p.valor} className="mt-0.5" />
            <span className="text-sm">
              <span className="font-medium">{p.titulo}</span>
              <span className="block text-muted-foreground">{p.descricao}</span>
            </span>
          </label>
        ))}
      </RadioGroup>
    </div>
  )
}

function CampoToken({
  acesso,
  token,
  obterToken,
  aoTrocar,
}: {
  acesso: AcessoMcp
  token: string | null
  obterToken: () => Promise<string>
  aoTrocar: Dispatch<string>
}) {
  const [visivel, setVisivel] = useState(false)

  async function alternarVisivel() {
    if (!visivel) {
      try {
        await obterToken()
      } catch (err) {
        toast.error((err as Error).message)
        return
      }
    }
    setVisivel(!visivel)
  }

  return (
    <div className="space-y-2">
      <Label htmlFor="token-mcp">Token</Label>
      <div className="flex flex-wrap items-center gap-2">
        <code
          id="token-mcp"
          className="min-w-0 flex-1 truncate rounded-md border bg-muted/50 px-3 py-2 font-mono text-sm"
        >
          {visivel && token ? token : `${acesso.prefixo}${TOKEN_OCULTO}`}
        </code>
        <Button
          variant="outline"
          size="icon"
          onClick={alternarVisivel}
          aria-label={visivel ? "Ocultar token" : "Mostrar token"}
        >
          {visivel ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </Button>
        <BotaoCopiar rotulo="Copiar token" obterTexto={obterToken} />
      </div>
      <p className="text-xs text-muted-foreground">
        Gerado em{" "}
        {acesso.token_gerado_em ? formatDateTime(acesso.token_gerado_em) : "—"}
        {" · "}
        {acesso.ultimo_uso_em
          ? `último uso em ${formatDateTime(acesso.ultimo_uso_em)}`
          : "ainda não usado"}
      </p>
      <TrocarToken
        aoTrocar={(novo) => {
          aoTrocar(novo)
          setVisivel(true)
        }}
      />
    </div>
  )
}

function TrocarToken({ aoTrocar }: { aoTrocar: Dispatch<string> }) {
  const trocar = useTrocarTokenMcp()
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" className="mt-2">
          <RefreshCw className="size-4" aria-hidden /> Trocar token
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Trocar o token?</AlertDialogTitle>
          <AlertDialogDescription>
            Um token novo é gerado e o atual para de funcionar na hora — os
            agentes configurados com ele vão precisar do novo.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              trocar.mutate(undefined, {
                onSuccess: (novo) => {
                  aoTrocar(novo)
                  toast.success("Token trocado.")
                },
                onError: (err) => toast.error(err.message),
              })
            }}
          >
            Trocar token
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function Endereco({ url }: { url: string }) {
  return (
    <div className="space-y-2">
      <Label htmlFor="url-mcp">Endereço do servidor MCP</Label>
      <div className="flex items-center gap-2">
        <code
          id="url-mcp"
          className="min-w-0 flex-1 truncate rounded-md border bg-muted/50 px-3 py-2 font-mono text-sm"
        >
          {url}
        </code>
        <BotaoCopiar
          rotulo="Copiar endereço"
          obterTexto={() => Promise.resolve(url)}
        />
      </div>
    </div>
  )
}

function BotaoCopiar({
  rotulo,
  obterTexto,
}: {
  rotulo: string
  obterTexto: () => Promise<string>
}) {
  const [copiado, setCopiado] = useState(false)
  return (
    <Button
      variant="outline"
      size="icon"
      aria-label={rotulo}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(await obterTexto())
          setCopiado(true)
          setTimeout(() => {
            setCopiado(false)
          }, 1500)
        } catch (err) {
          toast.error((err as Error).message || "Não foi possível copiar.")
        }
      }}
    >
      {copiado ? <Check className="size-4" /> : <Copy className="size-4" />}
    </Button>
  )
}

const MARCADOR = "SEU_TOKEN"

function snippets(url: string, comToken: boolean) {
  const header = comToken ? ` --header "Authorization: Bearer ${MARCADOR}"` : ""
  return [
    {
      id: "claude",
      rotulo: "Claude Code",
      texto: `claude mcp add --transport http mango ${url}${header}`,
    },
    {
      id: "codex",
      rotulo: "Codex",
      texto: comToken
        ? `# ~/.codex/config.toml\n[mcp_servers.mango]\nurl = "${url}"\nbearer_token_env_var = "MANGO_MCP_TOKEN"\n\n# no shell:\nexport MANGO_MCP_TOKEN="${MARCADOR}"`
        : `# ~/.codex/config.toml\n[mcp_servers.mango]\nurl = "${url}"`,
    },
    {
      id: "openwebui",
      rotulo: "Open WebUI",
      texto: `Configurações → Ferramentas (Tools) → adicionar conexão\nTipo: MCP (Streamable HTTP)\nURL: ${url}${comToken ? `\nAutenticação: Bearer\nToken: ${MARCADOR}` : ""}`,
    },
    {
      id: "json",
      rotulo: "Outros (JSON)",
      texto: JSON.stringify(
        {
          mcpServers: {
            mango: {
              command: "npx",
              args: [
                "-y",
                "mcp-remote",
                url,
                ...(comToken
                  ? ["--header", `Authorization: Bearer ${MARCADOR}`]
                  : []),
              ],
            },
          },
        },
        null,
        2
      ),
    },
  ]
}

/** Configuração pronta por cliente. O texto exibido traz o marcador; o botão copia já com o token
 * de verdade (buscado só no clique). */
function Snippets({
  url,
  token,
}: {
  url: string
  token: (() => Promise<string>) | null
}) {
  const itens = snippets(url, token !== null)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Conectar um agente</CardTitle>
        <CardDescription>
          Copie a configuração do seu cliente — o botão já inclui o token.
          Clientes que só falam stdio usam a opção JSON (via mcp-remote).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="claude">
          <div className="no-scrollbar overflow-x-auto overflow-y-hidden py-1">
            <TabsList>
              {itens.map((s) => (
                <TabsTrigger key={s.id} value={s.id}>
                  {s.rotulo}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          {itens.map((s) => (
            <TabsContent key={s.id} value={s.id} className="pt-3">
              <div className="relative">
                <pre className="overflow-x-auto rounded-md border bg-muted/50 p-3 pr-12 font-mono text-xs leading-relaxed">
                  {s.texto}
                </pre>
                <div className="absolute top-2 right-2">
                  <BotaoCopiar
                    rotulo={`Copiar configuração do ${s.rotulo}`}
                    obterTexto={async () =>
                      token
                        ? s.texto.replaceAll(MARCADOR, await token())
                        : s.texto
                    }
                  />
                </div>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  )
}
