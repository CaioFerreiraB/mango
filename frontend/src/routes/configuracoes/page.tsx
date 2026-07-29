import { ConexoesTab } from "@/components/configuracoes/conexoes-tab"
import { PerfilTab } from "@/components/configuracoes/perfil-tab"
import { PreferenciasTab } from "@/components/configuracoes/preferencias-tab"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export function ConfiguracoesPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Configurações</h1>
      <Tabs defaultValue="conexoes">
        <TabsList>
          <TabsTrigger value="conexoes">Conexões</TabsTrigger>
          <TabsTrigger value="perfil">Perfil</TabsTrigger>
          <TabsTrigger value="preferencias">Preferências do sistema</TabsTrigger>
        </TabsList>
        <TabsContent value="conexoes" className="pt-4">
          <ConexoesTab />
        </TabsContent>
        <TabsContent value="perfil" className="pt-4">
          <PerfilTab />
        </TabsContent>
        <TabsContent value="preferencias" className="pt-4">
          <PreferenciasTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
