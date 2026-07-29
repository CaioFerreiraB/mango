import { Plus, RefreshCw, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useCredenciais,
  useCriarCredencial,
  useCriarItem,
  useItens,
  useRemoverItem,
  useSincronizarItem,
  useTestarCredencial,
} from "@/lib/api/conexoes"
import {
  useDefinirBrapiToken,
  usePerfil,
  useRemoverBrapiToken,
  useTestarBrapiToken,
} from "@/lib/api/perfil"
import { formatDateTime } from "@/lib/format"

export function ConexoesTab() {
  const credenciais = useCredenciais()
  if (credenciais.isLoading) return <Skeleton className="h-40 w-full" />
  const credencial = credenciais.data?.[0]

  return (
    <div className="space-y-4">
      {credencial ? <CredencialConfigurada /> : <FormCredencial />}
      {credencial ? <ListaItens credencialId={credencial.id} /> : null}
      <BrapiTokenCard />
    </div>
  )
}

/** Token brapi.dev (write-only, cifrado) — habilita a evolução do valor da cota (FII), o comparativo
 *  com o IBOV e a reconstrução do histórico de preço da renda variável. O valor nunca é exibido. */
function BrapiTokenCard() {
  const perfil = usePerfil()
  const definir = useDefinirBrapiToken()
  const remover = useRemoverBrapiToken()
  const testar = useTestarBrapiToken()
  const [token, setToken] = useState("")
  const configurado = perfil.data?.brapi_token_configurado ?? false

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Token da brapi.dev</CardTitle>
        <CardDescription>
          Opcional. Habilita a evolução do valor da cota, o comparativo com o IBOV e a reconstrução
          do histórico de preço. O token é guardado cifrado e nunca é exibido de volta.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {perfil.isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : configurado ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Configurado.</span>
            <Button
              variant="outline"
              size="sm"
              disabled={testar.isPending}
              onClick={() =>
                testar.mutate(undefined, {
                  onSuccess: (valida) =>
                    valida
                      ? toast.success("Token válido.")
                      : toast.error("Token inválido — verifique na brapi.dev."),
                  onError: () => toast.error("Não foi possível testar agora."),
                })
              }
            >
              Testar token
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={remover.isPending}
              onClick={() =>
                remover.mutate(undefined, {
                  onSuccess: () => toast.success("Token removido."),
                  onError: (err) => toast.error(err.message),
                })
              }
            >
              <Trash2 className="size-4" aria-hidden /> Remover
            </Button>
          </div>
        ) : (
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              definir.mutate(token, {
                onSuccess: () => {
                  toast.success("Token salvo.")
                  setToken("")
                },
                onError: (err) => toast.error(err.message),
              })
            }}
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="brapi_token">Token</Label>
              <Input
                id="brapi_token"
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={!token || definir.isPending} className="self-start">
              Salvar token
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

function FormCredencial() {
  const criar = useCriarCredencial()
  const [clientId, setClientId] = useState("")
  const [clientSecret, setClientSecret] = useState("")

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Credencial do Pluggy</CardTitle>
        <CardDescription>
          Crie um app no Pluggy e informe o clientId e o clientSecret. O segredo
          é guardado cifrado e nunca é exibido de volta.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            criar.mutate(
              { client_id: clientId, client_secret: clientSecret },
              {
                onSuccess: () => {
                  toast.success("Credencial salva.")
                  setClientId("")
                  setClientSecret("")
                },
                onError: (err) => toast.error(err.message),
              }
            )
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="client_id">clientId</Label>
            <Input
              id="client_id"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              required
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="client_secret">clientSecret</Label>
            <Input
              id="client_secret"
              type="password"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              required
            />
          </div>
          <Button
            type="submit"
            disabled={criar.isPending}
            className="self-start"
          >
            Salvar credencial
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function CredencialConfigurada() {
  const testar = useTestarCredencial()
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle className="text-base">Credencial do Pluggy</CardTitle>
          <CardDescription>
            Configurada. O segredo fica cifrado no servidor.
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={testar.isPending}
          onClick={() =>
            testar.mutate(undefined, {
              onSuccess: (valida) =>
                valida
                  ? toast.success("Credencial válida.")
                  : toast.error(
                      "Credencial inválida — verifique clientId/clientSecret."
                    ),
              onError: () => toast.error("Não foi possível testar agora."),
            })
          }
        >
          Testar credencial
        </Button>
      </CardHeader>
    </Card>
  )
}

function ListaItens({ credencialId }: { credencialId: number }) {
  const itens = useItens()
  const sincronizar = useSincronizarItem()
  const remover = useRemoverItem()

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle className="text-base">Conexões</CardTitle>
          <CardDescription>
            Contas conectadas pelo Meu Pluggy (itemId).
          </CardDescription>
        </div>
        <DialogAdicionar credencialId={credencialId} />
      </CardHeader>
      <CardContent className="space-y-2">
        {itens.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (itens.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma conexão. Adicione um itemId.
          </p>
        ) : (
          itens.data!.map((it) => (
            <div
              key={it.id}
              className="flex items-center justify-between gap-3 rounded-lg border p-3"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {it.connector_nome ?? "Conexão"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {it.status ?? "—"}
                  {it.ultimo_sync_em
                    ? ` · sync ${formatDateTime(it.ultimo_sync_em)}`
                    : ""}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Atualizar conexão"
                  disabled={sincronizar.isPending}
                  onClick={() => sincronizar.mutate(it.id)}
                >
                  <RefreshCw className="size-4" aria-hidden />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Remover conexão"
                  onClick={() =>
                    remover.mutate(it.id, {
                      onSuccess: () => toast.success("Conexão removida."),
                      onError: () => toast.error("Não foi possível remover."),
                    })
                  }
                >
                  <Trash2 className="size-4" aria-hidden />
                </Button>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}

function DialogAdicionar({ credencialId }: { credencialId: number }) {
  const criarItem = useCriarItem()
  const sincronizar = useSincronizarItem()
  const [itemId, setItemId] = useState("")
  const [aberto, setAberto] = useState(false)

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" aria-hidden /> Adicionar
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Adicionar conexão</DialogTitle>
          <DialogDescription>
            Cole o itemId obtido no Meu Pluggy. Ao adicionar, sincronizamos as
            contas.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="item_id">itemId</Label>
          <Input
            id="item_id"
            value={itemId}
            onChange={(e) => setItemId(e.target.value)}
          />
        </div>
        <DialogFooter>
          <Button
            disabled={!itemId || criarItem.isPending}
            onClick={() =>
              criarItem.mutate(
                { credencial_id: credencialId, pluggy_item_id: itemId },
                {
                  onSuccess: (item) => {
                    setItemId("")
                    setAberto(false)
                    sincronizar.mutate(item.id) // valida o itemId + puxa os dados
                  },
                  onError: (err) => toast.error(err.message),
                }
              )
            }
          >
            Adicionar e sincronizar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
