import { IaTab } from "@/components/configuracoes/ia-tab"
import { useSearchParams } from "react-router"

import { PageHeader } from "@/components/common/page-header"
import { CategoriasTab } from "@/components/configuracoes/categorias-tab"
import { ConexoesTab } from "@/components/configuracoes/conexoes-tab"
import { McpTab } from "@/components/configuracoes/mcp-tab"
import { PerfilTab } from "@/components/configuracoes/perfil-tab"
import { PreferenciasTab } from "@/components/configuracoes/preferencias-tab"
import { SegurancaTab } from "@/components/configuracoes/seguranca-tab"
import { SistemaTab } from "@/components/configuracoes/sistema-tab"
import { TelegramTab } from "@/components/configuracoes/telegram-tab"
import { UsuariosTab } from "@/components/configuracoes/usuarios-tab"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useMe, useSetupStatus } from "@/lib/api/auth"

export function ConfiguracoesPage() {
  const me = useMe()
  const status = useSetupStatus()
  // Conexões (bancos/brapi) só faz sentido pra quem enxerga contas/investimentos (§4.11).
  const podeVerConexoes = (me.data?.tipo ?? "completo") === "completo"
  // 2FA só existe no self-hosted (modo local não tem login nem senha) — qualquer tipo de conta.
  const podeVerSeguranca = status.data?.app_mode === "self_hosted"
  // Gestão de usuários e configs da instância são só do dono, e só existem no self-hosted.
  const podeAdministrarInstancia =
    me.data?.is_admin === true && status.data?.app_mode === "self_hosted"
  const abaPadrao = podeVerConexoes ? "conexoes" : "perfil"

  // Aba na URL (`?aba=categorias`): permite linkar direto de outra tela — o drawer da transação
  // manda para as regras de categorização. `key` remonta quando as permissões chegam e mudam o
  // padrão.
  const [params, setParams] = useSearchParams()
  // Só as abas que ESTA conta enxerga. Sem a checagem, `?aba=xyz` — ou um link com `?aba=usuarios`
  // aberto por quem não é admin — deixa nenhum trigger ativo e nenhum conteúdo renderizado: a
  // página fica só com a faixa de abas. Links de configuração são compartilháveis, então o estado
  // é alcançável; cair no padrão é o comportamento que não confunde.
  const abas = [
    { valor: "conexoes", rotulo: "Conexões", ok: podeVerConexoes },
    { valor: "telegram", rotulo: "Telegram", ok: true },
    { valor: "ia", rotulo: "Inteligência artificial", ok: podeVerConexoes },
    { valor: "perfil", rotulo: "Perfil", ok: true },
    { valor: "preferencias", rotulo: "Preferências", ok: true },
    { valor: "categorias", rotulo: "Categorias", ok: true },
    { valor: "mcp", rotulo: "MCP", ok: true },
    { valor: "seguranca", rotulo: "Segurança", ok: podeVerSeguranca },
    { valor: "usuarios", rotulo: "Usuários", ok: podeAdministrarInstancia },
    { valor: "sistema", rotulo: "Sistema", ok: podeAdministrarInstancia },
  ].filter((a) => a.ok)
  const abasVisiveis = abas.map((a) => a.valor)
  const naUrl = params.get("aba")
  const aba = naUrl !== null && abasVisiveis.includes(naUrl) ? naUrl : abaPadrao

  function trocarAba(valor: string) {
    setParams(
      (atual) => {
        const proximo = new URLSearchParams(atual)
        proximo.set("aba", valor)
        return proximo
      },
      { replace: true } // trocar de aba não deve encher o histórico do navegador
    )
  }

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader
        titulo="Configurações"
        descricao="Conexões, integrações, perfil e preferências do app."
      />
      <Tabs value={aba} onValueChange={trocarAba} key={abaPadrao}>
        {/* Mobile: as até 10 abas viram um seletor (uma linha, sem quebra torta); a partir de
            `md`, abas de linha como no resto do app. */}
        <Select value={aba} onValueChange={trocarAba}>
          <SelectTrigger className="w-full md:hidden" aria-label="Seção">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {abas.map((a) => (
              <SelectItem key={a.valor} value={a.valor}>
                {a.rotulo}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <TabsList
          variant="line"
          className="hidden w-full justify-start border-b md:flex"
        >
          {abas.map((a) => (
            <TabsTrigger key={a.valor} value={a.valor}>
              {a.rotulo}
            </TabsTrigger>
          ))}
        </TabsList>
        {podeVerConexoes ? (
          <TabsContent value="conexoes" className="pt-4">
            <ConexoesTab />
          </TabsContent>
        ) : null}
        <TabsContent value="telegram" className="pt-4">
          <TelegramTab />
        </TabsContent>
        {podeVerConexoes ? (
          <TabsContent value="ia" className="pt-4">
            <IaTab />
          </TabsContent>
        ) : null}
        <TabsContent value="perfil" className="pt-4">
          <PerfilTab />
        </TabsContent>
        <TabsContent value="preferencias" className="pt-4">
          <PreferenciasTab />
        </TabsContent>
        <TabsContent value="categorias" className="pt-4">
          <CategoriasTab />
        </TabsContent>
        <TabsContent value="mcp" className="pt-4">
          <McpTab />
        </TabsContent>
        {podeVerSeguranca ? (
          <TabsContent value="seguranca" className="pt-4">
            <SegurancaTab />
          </TabsContent>
        ) : null}
        {podeAdministrarInstancia ? (
          <TabsContent value="usuarios" className="pt-4">
            <UsuariosTab />
          </TabsContent>
        ) : null}
        {podeAdministrarInstancia ? (
          <TabsContent value="sistema" className="pt-4">
            <SistemaTab />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  )
}
