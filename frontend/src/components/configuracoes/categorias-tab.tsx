import { useMemo } from "react"

import { EmptyState } from "@/components/common/empty-state"
import { CategoriasPadraoCard } from "@/components/configuracoes/categorias-padrao-card"
import { CategoriasPersonalizadasCard } from "@/components/configuracoes/categorias-personalizadas-card"
import { RegrasCategorizacaoCard } from "@/components/configuracoes/regras-categorizacao-card"
import { Skeleton } from "@/components/ui/skeleton"
import { useCategorias } from "@/lib/api/categorias"

/** Aba "Categorias" em Configurações (§4.5).
 *
 * Três seções separadas de propósito: o que o usuário criou (renomeia e exclui), o que vem do
 * banco (só liga/desliga — a linha é compartilhada entre usuários) e as regras que ligam nome de
 * transação a categoria.
 */
export function CategoriasTab() {
  const categorias = useCategorias()

  const { personalizadas, doBanco } = useMemo(() => {
    const todas = categorias.data ?? []
    return {
      personalizadas: todas.filter((c) => c.personalizada),
      doBanco: todas.filter((c) => !c.personalizada),
    }
  }, [categorias.data])

  if (categorias.isError)
    return <EmptyState title="Não foi possível carregar as categorias" />
  if (categorias.isLoading) return <Skeleton className="h-96 w-full" />

  return (
    <div className="space-y-4">
      <CategoriasPersonalizadasCard categorias={personalizadas} />
      <CategoriasPadraoCard categorias={doBanco} />
      <RegrasCategorizacaoCard />
    </div>
  )
}
