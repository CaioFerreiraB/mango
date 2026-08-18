import { toast } from "sonner"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import {
  useAtualizarConfiguracaoSistema,
  useConfiguracaoSistema,
} from "@/lib/api/configuracoes"

/** Aba "Sistema" em Configurações, só pro dono da instância (§4.11-otimização). */
export function SistemaTab() {
  const config = useConfiguracaoSistema()
  const atualizar = useAtualizarConfiguracaoSistema()

  if (config.isLoading || !config.data) return <Skeleton className="h-32 w-full" />

  function alternar(v: boolean) {
    atualizar.mutate(v, {
      onSuccess: () =>
        toast.success(v ? "Otimização de transações ativada." : "Otimização de transações desativada."),
      onError: (err) => toast.error(err.message),
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Divisão de contas</CardTitle>
      </CardHeader>
      <CardContent>
        <label className="flex items-start justify-between gap-4">
          <span className="flex flex-col gap-0.5">
            <span className="text-sm font-medium">Otimizar transações</span>
            <span className="text-sm text-muted-foreground">
              Simplifica cadeias de dívida — se A deve a B e B deve a C, o saldo passa a
              mostrar A devendo a C diretamente. Não altera nenhum lançamento, só como o saldo
              é exibido.
            </span>
          </span>
          <Switch checked={config.data.otimizar_transacoes_divisao} onCheckedChange={alternar} />
        </label>
      </CardContent>
    </Card>
  )
}
