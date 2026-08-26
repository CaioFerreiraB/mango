import { QRCodeSVG } from "qrcode.react"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { usePerfil, type Perfil } from "@/lib/api/perfil"
import {
  useConfirmarTotp,
  useDesabilitarTotpLogin,
  useHabilitarTotpLogin,
  useIniciarTotp,
} from "@/lib/api/totp"

/** 2FA em Configurações (§5.2, #15): cadastrar/trocar (wizard com step-up de senha) e
 *  habilitar/desabilitar a exigência no login. Só existe no self-hosted — a página só monta
 *  esta aba nesse modo (ver `routes/configuracoes/page.tsx`). */
export function SegurancaTab() {
  const perfil = usePerfil()
  if (perfil.isLoading || !perfil.data)
    return <Skeleton className="h-48 w-full" />
  // Chaveado pelo id: os diálogos reiniciam o próprio estado ao fechar (sem effect).
  return <SegurancaContent key={perfil.data.id} perfil={perfil.data} />
}

function SegurancaContent({ perfil }: { perfil: Perfil }) {
  const [trocarAberto, setTrocarAberto] = useState(false)
  const [desabilitarAberto, setDesabilitarAberto] = useState(false)
  const habilitar = useHabilitarTotpLogin()

  function ligar() {
    habilitar.mutate(undefined, {
      onSuccess: () => toast.success("2FA passa a ser exigido no login."),
      onError: (err) => toast.error(err.message),
    })
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Verificação em duas etapas (2FA)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!perfil.totp_configurado ? (
            <>
              <p className="text-sm text-muted-foreground">
                Sem 2FA configurado, não é possível recuperar a senha esquecida.
              </p>
              <Button onClick={() => setTrocarAberto(true)}>Ativar 2FA</Button>
            </>
          ) : (
            <>
              <div className="flex items-center justify-between gap-4 rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">Exigir código no login</p>
                  <p className="text-xs text-muted-foreground">
                    Desligado, o login pede só usuário e senha — a recuperação
                    de senha continua exigindo o código.
                  </p>
                </div>
                <Switch
                  checked={perfil.totp_login_habilitado}
                  onCheckedChange={(v) =>
                    v ? ligar() : setDesabilitarAberto(true)
                  }
                  disabled={habilitar.isPending}
                />
              </div>
              <Button variant="outline" onClick={() => setTrocarAberto(true)}>
                Trocar 2FA
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      <TrocarTotpDialog
        aberto={trocarAberto}
        onOpenChange={setTrocarAberto}
        jaConfigurado={perfil.totp_configurado}
      />
      <DesabilitarTotpDialog
        aberto={desabilitarAberto}
        onOpenChange={setDesabilitarAberto}
      />
    </div>
  )
}

/** Cadastrar (1ª vez) ou trocar o 2FA — mesmo wizard, step-up de senha → QR → código. */
function TrocarTotpDialog({
  aberto,
  onOpenChange,
  jaConfigurado,
}: {
  aberto: boolean
  onOpenChange: (v: boolean) => void
  jaConfigurado: boolean
}) {
  const [etapa, setEtapa] = useState<"senha" | "qr" | "codigo">("senha")
  const [senhaAtual, setSenhaAtual] = useState("")
  const [codigo, setCodigo] = useState("")
  const [erro, setErro] = useState<string | null>(null)
  const [dados, setDados] = useState<{
    ticket: string
    totp_secret: string
    totp_provisioning_uri: string
  } | null>(null)
  const iniciar = useIniciarTotp()
  const confirmar = useConfirmarTotp()

  function fechar(v: boolean) {
    onOpenChange(v)
    if (!v) {
      setEtapa("senha")
      setSenhaAtual("")
      setCodigo("")
      setErro(null)
      setDados(null)
    }
  }

  async function enviarSenha(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      const resp = await iniciar.mutateAsync(senhaAtual)
      setDados(resp)
      setEtapa("qr")
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Senha atual incorreta.")
    }
  }

  async function confirmarCodigo() {
    if (!dados) return
    setErro(null)
    try {
      await confirmar.mutateAsync({ ticket: dados.ticket, codigo_totp: codigo })
      toast.success(jaConfigurado ? "2FA trocado." : "2FA ativado.")
      fechar(false)
    } catch (err) {
      setErro(
        err instanceof Error
          ? err.message
          : "Código incorreto. Confira o app autenticador e tente de novo."
      )
    }
  }

  return (
    <Dialog open={aberto} onOpenChange={fechar}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {jaConfigurado ? "Trocar 2FA" : "Ativar 2FA"}
          </DialogTitle>
        </DialogHeader>

        {etapa === "senha" ? (
          <form onSubmit={enviarSenha} className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Confirme sua senha atual para{" "}
              {jaConfigurado ? "trocar" : "cadastrar"} o 2FA.
            </p>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="senha_atual">Senha atual</Label>
              <Input
                id="senha_atual"
                type="password"
                autoComplete="current-password"
                autoFocus
                value={senhaAtual}
                onChange={(e) => setSenhaAtual(e.target.value)}
              />
            </div>
            {erro ? (
              <p role="alert" className="text-sm text-destructive">
                {erro}
              </p>
            ) : null}
            <DialogFooter>
              <Button type="submit" disabled={iniciar.isPending || !senhaAtual}>
                {iniciar.isPending ? "Confirmando…" : "Continuar"}
              </Button>
            </DialogFooter>
          </form>
        ) : etapa === "qr" && dados ? (
          <div className="flex flex-col items-center gap-4">
            <p className="text-sm text-muted-foreground">
              Escaneie o QR code no seu app autenticador (Google Authenticator,
              Aegis, etc.).
            </p>
            <div className="rounded-lg bg-white p-3">
              <QRCodeSVG value={dados.totp_provisioning_uri} size={180} />
            </div>
            <div className="w-full">
              <Label>Ou insira a chave manualmente</Label>
              <code className="mt-1 block rounded-md bg-muted px-2 py-1.5 text-xs break-all">
                {dados.totp_secret}
              </code>
            </div>
            <Button className="w-full" onClick={() => setEtapa("codigo")}>
              Já escaneei
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="codigo_totp">Código do autenticador</Label>
              <Input
                id="codigo_totp"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="000000"
                autoFocus
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && codigo.length >= 6) confirmarCodigo()
                }}
              />
            </div>
            {erro ? (
              <p role="alert" className="text-sm text-destructive">
                {erro}
              </p>
            ) : null}
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setEtapa("qr")}
                disabled={confirmar.isPending}
              >
                Voltar
              </Button>
              <Button
                onClick={confirmarCodigo}
                disabled={confirmar.isPending || codigo.length < 6}
              >
                {confirmar.isPending ? "Verificando…" : "Verificar e concluir"}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

/** Desligar a exigência de código no login — step-up de senha (o 2FA continua configurado). */
function DesabilitarTotpDialog({
  aberto,
  onOpenChange,
}: {
  aberto: boolean
  onOpenChange: (v: boolean) => void
}) {
  const [senhaAtual, setSenhaAtual] = useState("")
  const [erro, setErro] = useState<string | null>(null)
  const desabilitar = useDesabilitarTotpLogin()

  function fechar(v: boolean) {
    onOpenChange(v)
    if (!v) {
      setSenhaAtual("")
      setErro(null)
    }
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      await desabilitar.mutateAsync(senhaAtual)
      toast.success("2FA não é mais exigido no login.")
      fechar(false)
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Senha atual incorreta.")
    }
  }

  return (
    <Dialog open={aberto} onOpenChange={fechar}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Desligar a exigência de código no login</DialogTitle>
        </DialogHeader>
        <form onSubmit={enviar} className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Confirme sua senha atual. O 2FA continua configurado — só deixa de
            ser pedido no login.
          </p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="senha_atual_desabilitar">Senha atual</Label>
            <Input
              id="senha_atual_desabilitar"
              type="password"
              autoComplete="current-password"
              autoFocus
              value={senhaAtual}
              onChange={(e) => setSenhaAtual(e.target.value)}
            />
          </div>
          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}
          <DialogFooter>
            <Button
              type="submit"
              disabled={desabilitar.isPending || !senhaAtual}
            >
              {desabilitar.isPending ? "Confirmando…" : "Desligar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
