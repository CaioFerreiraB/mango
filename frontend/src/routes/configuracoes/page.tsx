import { useSearchParams } from "react-router"

import { CategoriasTab } from "@/components/configuracoes/categorias-tab"
import { ConexoesTab } from "@/components/configuracoes/conexoes-tab"
import { PerfilTab } from "@/components/configuracoes/perfil-tab"
import { PreferenciasTab } from "@/components/configuracoes/preferencias-tab"
import { SegurancaTab } from "@/components/configuracoes/seguranca-tab"
import { SistemaTab } from "@/components/configuracoes/sistema-tab"
import { UsuariosTab } from "@/components/configuracoes/usuarios-tab"
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
  const aba = params.get("aba") ?? abaPadrao

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
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Configurações</h1>
      <Tabs value={aba} onValueChange={trocarAba} key={abaPadrao}>
        {/* Faixa rolável: com 7 abas a lista estoura telas estreitas e arrastava a página inteira.
            overflow-y-hidden porque overflow-x-auto promove overflow-y a auto e o after:bottom-[-5px]
            do trigger criaria scroll vertical; py-1 dá folga ao anel de foco. Ver carteira.tsx. */}
        <div className="no-scrollbar overflow-x-auto overflow-y-hidden py-1">
          <TabsList>
            {podeVerConexoes ? (
              <TabsTrigger value="conexoes">Conexões</TabsTrigger>
            ) : null}
            <TabsTrigger value="perfil">Perfil</TabsTrigger>
            <TabsTrigger value="preferencias">Preferências</TabsTrigger>
            <TabsTrigger value="categorias">Categorias</TabsTrigger>
            {podeVerSeguranca ? (
              <TabsTrigger value="seguranca">Segurança</TabsTrigger>
            ) : null}
            {podeAdministrarInstancia ? (
              <TabsTrigger value="usuarios">Usuários</TabsTrigger>
            ) : null}
            {podeAdministrarInstancia ? (
              <TabsTrigger value="sistema">Sistema</TabsTrigger>
            ) : null}
          </TabsList>
        </div>
        {podeVerConexoes ? (
          <TabsContent value="conexoes" className="pt-4">
            <ConexoesTab />
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
