import { Search, SlidersHorizontal } from "lucide-react"
import { useState } from "react"
import { useSearchParams } from "react-router"

import { EmptyState } from "@/components/common/empty-state"
import { CategoriaSelect } from "@/components/transacoes/categoria-select"
import { TransacoesTabela } from "@/components/transacoes/transacoes-tabela"
import { SyncButton } from "@/components/sync-button"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useAssinaturas } from "@/lib/api/assinaturas"
import { useContas } from "@/lib/api/contas"
import { useTransacoes } from "@/lib/api/transacoes"

const LIMIT = 25
const TODAS = "__todas__"
const QUALQUER = "__qualquer__"
const SEM = "__sem__"

/** Números de página a exibir (1-based), com "gap" (…) nos vãos. Sempre 1, atual±1 e a última. */
function janelaPaginas(atual: number, total: number): (number | "gap")[] {
  const alvos = new Set([1, total, atual, atual - 1, atual + 1])
  const visiveis = [...alvos]
    .filter((p) => p >= 1 && p <= total)
    .sort((a, b) => a - b)
  const saida: (number | "gap")[] = []
  let anterior = 0
  for (const p of visiveis) {
    if (p - anterior > 1) saida.push("gap")
    saida.push(p)
    anterior = p
  }
  return saida
}

export function TransacoesPage() {
  const [params] = useSearchParams()
  const [busca, setBusca] = useState("")
  const [contaId, setContaId] = useState<number | null>(
    params.get("conta_id") ? Number(params.get("conta_id")) : null
  )
  const [categoriaId, setCategoriaId] = useState<string | null>(
    params.get("categoria_id")
  )
  const [tipo, setTipo] = useState<"DEBIT" | "CREDIT" | null>(null)
  // `revisada=false` é o link antigo (§4.3, antes da data de corte) — continua entrando aqui para
  // não quebrar link salvo ou favoritado.
  const [soNaoRevisadas, setSoNaoRevisadas] = useState(
    params.get("pendente") === "true" || params.get("revisada") === "false"
  )
  const [transf, setTransf] = useState<"todas" | "ocultar" | "so">("todas")
  // "__todas__" · "__qualquer__" (com assinatura) · "__sem__" (sem) · id da assinatura.
  const [assinaturaFiltro, setAssinaturaFiltro] = useState(TODAS)
  const [page, setPage] = useState(0)

  const contas = useContas()
  const assinaturas = useAssinaturas()

  function reset<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v)
      setPage(0)
    }
  }

  const assinaturaId = /^\d+$/.test(assinaturaFiltro)
    ? Number(assinaturaFiltro)
    : undefined
  const temAssinatura =
    assinaturaFiltro === QUALQUER
      ? true
      : assinaturaFiltro === SEM
        ? false
        : undefined

  const listagem = useTransacoes({
    busca: busca || undefined,
    conta_id: contaId ?? undefined,
    categoria_id: categoriaId ?? undefined,
    tipo: tipo ?? undefined,
    pendente_revisao: soNaoRevisadas ? true : undefined,
    eh_transferencia:
      transf === "ocultar" ? false : transf === "so" ? true : undefined,
    assinatura_id: assinaturaId,
    tem_assinatura: temAssinatura,
    limit: LIMIT,
    offset: page * LIMIT,
  })

  const filtrosAvancados =
    (tipo !== null ? 1 : 0) +
    (transf !== "todas" ? 1 : 0) +
    (assinaturaFiltro !== TODAS ? 1 : 0)

  const total = listagem.data?.total ?? 0
  const paginas = Math.max(1, Math.ceil(total / LIMIT))
  const paginaAtual = page + 1

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Transações</h1>
        <SyncButton />
      </header>

      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search
              className="absolute top-2.5 left-2.5 size-4 text-muted-foreground"
              aria-hidden
            />
            <Input
              placeholder="Buscar descrição ou estabelecimento"
              value={busca}
              onChange={(e) => reset(setBusca)(e.target.value)}
              className="h-9 w-full pl-8"
            />
          </div>
          <label className="hidden shrink-0 items-center gap-2 text-sm text-muted-foreground sm:flex">
            <Switch
              checked={soNaoRevisadas}
              onCheckedChange={(c) => reset(setSoNaoRevisadas)(c)}
            />
            Só pendentes
          </label>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="shrink-0">
                <SlidersHorizontal className="size-4" />
                Mais filtros
                {filtrosAvancados > 0 ? (
                  <Badge variant="secondary" className="px-1.5">
                    {filtrosAvancados}
                  </Badge>
                ) : null}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-72 space-y-3">
              <label className="flex items-center justify-between gap-2 text-sm sm:hidden">
                Só pendentes
                <Switch
                  checked={soNaoRevisadas}
                  onCheckedChange={(c) => reset(setSoNaoRevisadas)(c)}
                />
              </label>
              <div className="space-y-1.5">
                <Label>Tipo</Label>
                <Select
                  value={tipo ?? TODAS}
                  onValueChange={(v) =>
                    reset(setTipo)(
                      v === TODAS ? null : (v as "DEBIT" | "CREDIT")
                    )
                  }
                >
                  <SelectTrigger size="sm" className="w-full">
                    <SelectValue placeholder="Tipo" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={TODAS}>Entradas e saídas</SelectItem>
                    <SelectItem value="CREDIT">Só entradas</SelectItem>
                    <SelectItem value="DEBIT">Só saídas</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Transferências</Label>
                <Select
                  value={transf}
                  onValueChange={(v) => reset(setTransf)(v as typeof transf)}
                >
                  <SelectTrigger size="sm" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todas">Com transferências</SelectItem>
                    <SelectItem value="ocultar">
                      Ocultar transferências
                    </SelectItem>
                    <SelectItem value="so">Só transferências</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Assinatura</Label>
                <Select
                  value={assinaturaFiltro}
                  onValueChange={reset(setAssinaturaFiltro)}
                >
                  <SelectTrigger size="sm" className="w-full">
                    <SelectValue placeholder="Assinatura" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={TODAS}>Todas</SelectItem>
                    <SelectItem value={QUALQUER}>
                      Qualquer assinatura
                    </SelectItem>
                    <SelectItem value={SEM}>Sem assinatura</SelectItem>
                    {(assinaturas.data ?? []).map((a) => (
                      <SelectItem key={a.id} value={String(a.id)}>
                        {a.nome}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </PopoverContent>
          </Popover>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Select
            value={contaId === null ? TODAS : String(contaId)}
            onValueChange={(v) =>
              reset(setContaId)(v === TODAS ? null : Number(v))
            }
          >
            <SelectTrigger size="sm" className="w-full">
              <SelectValue placeholder="Conta" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODAS}>Todas as contas</SelectItem>
              {(contas.data ?? []).map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.marketing_name ?? c.nome ?? c.pluggy_account_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <CategoriaSelect
            className="w-full"
            incluirTodas
            value={categoriaId}
            onChange={reset(setCategoriaId)}
          />
        </div>
      </div>

      {listagem.isError ? (
        <EmptyState title="Não foi possível carregar as transações" />
      ) : listagem.isLoading ? (
        <Skeleton className="h-72 w-full" />
      ) : total === 0 ? (
        <EmptyState
          icon={Search}
          title="Nenhuma transação encontrada"
          description="Ajuste os filtros ou atualize a conexão para importar novas transações."
        >
          <SyncButton />
        </EmptyState>
      ) : (
        <>
          <TransacoesTabela items={listagem.data!.items} />

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <span>
              {total} transaç{total === 1 ? "ão" : "ões"}
            </span>
            {paginas > 1 ? (
              <Pagination className="mx-0 w-auto">
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      href="#"
                      text="Anterior"
                      aria-disabled={page === 0}
                      className={
                        page === 0 ? "pointer-events-none opacity-50" : ""
                      }
                      onClick={(e) => {
                        e.preventDefault()
                        if (page > 0) setPage(page - 1)
                      }}
                    />
                  </PaginationItem>
                  {janelaPaginas(paginaAtual, paginas).map((p, i) =>
                    p === "gap" ? (
                      <PaginationItem key={`gap-${i}`}>
                        <PaginationEllipsis />
                      </PaginationItem>
                    ) : (
                      <PaginationItem key={p}>
                        <PaginationLink
                          href="#"
                          isActive={p === paginaAtual}
                          onClick={(e) => {
                            e.preventDefault()
                            setPage(p - 1)
                          }}
                        >
                          {p}
                        </PaginationLink>
                      </PaginationItem>
                    )
                  )}
                  <PaginationItem>
                    <PaginationNext
                      href="#"
                      text="Próxima"
                      aria-disabled={paginaAtual >= paginas}
                      className={
                        paginaAtual >= paginas
                          ? "pointer-events-none opacity-50"
                          : ""
                      }
                      onClick={(e) => {
                        e.preventDefault()
                        if (paginaAtual < paginas) setPage(page + 1)
                      }}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            ) : null}
          </div>
        </>
      )}
    </div>
  )
}
