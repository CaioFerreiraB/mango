import {
  ArrowRightLeft,
  CreditCard,
  Landmark,
  Search,
  Settings,
} from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { Valor } from "@/components/common/valor"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  dashboardItem,
  investimentosSection,
  navSections,
  navSectionsDivisaoOnly,
  settingsItem,
  type NavItem,
} from "@/config/nav"
import { useMe } from "@/lib/api/auth"
import { useContas } from "@/lib/api/contas"
import { useFaturas } from "@/lib/api/faturas"
import {
  descricaoExibida,
  ehLancamento,
  useTransacoes,
  valorEfetivoCentavos,
} from "@/lib/api/transacoes"
import { formatDate } from "@/lib/format"
import { normalizarBusca } from "@/lib/texto"

// ponytail: abas de admin/segurança ficam de fora (dependem de modo/permissão); a página de
// configurações cai na aba padrão se o link apontar para uma aba que a conta não vê.
const ABAS_CONFIG = [
  ["conexoes", "Conexões (Open Finance)"],
  ["ia", "Inteligência artificial"],
  ["telegram", "Telegram"],
  ["perfil", "Perfil"],
  ["preferencias", "Preferências (cor, avatar, alertas)"],
  ["categorias", "Categorias e regras"],
  ["mcp", "MCP"],
] as const

const MAX_TRANSACOES = 8

function contem(texto: string | null | undefined, termo: string): boolean {
  return normalizarBusca(texto).includes(termo)
}

/** Atalho ⌘K/Ctrl+K e `/` (fora de campos de texto) abrem a busca. */
function useAtalho(abrir: () => void) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const alvo = e.target as HTMLElement | null
      const digitando =
        alvo?.isContentEditable ||
        ["INPUT", "TEXTAREA", "SELECT"].includes(alvo?.tagName ?? "")
      if (
        (e.key === "k" && (e.metaKey || e.ctrlKey)) ||
        (e.key === "/" && !digitando)
      ) {
        e.preventDefault()
        abrir()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [abrir])
}

/** Busca global do header: páginas, configurações, contas, faturas e transações. */
export function BuscaGlobal() {
  const [aberta, setAberta] = useState(false)
  useAtalho(() => setAberta(true))

  return (
    <>
      {/* Desktop: campo-gatilho; mobile: só a lupa (a topbar é estreita). */}
      <Button
        variant="outline"
        onClick={() => setAberta(true)}
        className="hidden h-9 w-full max-w-sm justify-start gap-2 bg-muted/40 font-normal text-muted-foreground shadow-none md:flex"
      >
        <Search aria-hidden />
        <span className="truncate">Buscar transações, contas, páginas…</span>
        <kbd className="ml-auto rounded border bg-background px-1.5 font-sans text-[0.7rem]">
          Ctrl K
        </kbd>
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setAberta(true)}
        className="md:hidden"
        aria-label="Buscar"
      >
        <Search aria-hidden />
      </Button>
      <CommandDialog
        open={aberta}
        onOpenChange={setAberta}
        title="Buscar"
        className="sm:max-w-xl"
        description="Busque páginas, configurações, contas, faturas e transações"
      >
        {/* Montado só aberto: as queries de faturas/transações não rodam à toa. */}
        {aberta ? <Resultados fechar={() => setAberta(false)} /> : null}
      </CommandDialog>
    </>
  )
}

function Resultados({ fechar }: { fechar: () => void }) {
  const navigate = useNavigate()
  const me = useMe()
  const [texto, setTexto] = useState("")
  const [termoServidor, setTermoServidor] = useState("")
  const termo = normalizarBusca(texto)

  // Debounce da busca no servidor; local filtra a cada tecla.
  useEffect(() => {
    const t = setTimeout(() => setTermoServidor(texto.trim()), 250)
    return () => clearTimeout(t)
  }, [texto])

  const somenteDivisao = me.data?.tipo === "divisao"
  const contas = useContas()
  const faturas = useFaturas()
  const buscaTx = termoServidor.length >= 2 && !somenteDivisao
  const transacoes = useTransacoes(
    // Mesmo recorte padrão da tela de destino: senão o resultado (parcela futura, pagamento de
    // fatura) some ao abrir `/transacoes?id=` e o drawer não acha a transação.
    {
      busca: termoServidor,
      limit: MAX_TRANSACOES,
      ocultar_futuras: true,
      ocultar_pagamento_fatura: true,
    },
    { enabled: buscaTx }
  )

  function ir(url: string) {
    fechar()
    navigate(url)
  }

  const paginas: NavItem[] = somenteDivisao
    ? [...navSectionsDivisaoOnly.flatMap((s) => s.items), settingsItem]
    : [
        dashboardItem,
        ...navSections.flatMap((s) => s.items),
        ...investimentosSection.items,
        settingsItem,
      ]
  const paginasFiltradas = paginas.filter((p) => contem(p.title, termo))
  const abas = somenteDivisao
    ? ABAS_CONFIG.filter(([id]) => id !== "conexoes" && id !== "ia")
    : ABAS_CONFIG
  const abasFiltradas = abas.filter(([, rotulo]) =>
    contem(`configurações ${rotulo}`, termo)
  )

  const listaContas = somenteDivisao ? [] : (contas.data ?? [])
  const nomeConta = new Map(
    listaContas.map((c) => [c.id, c.marketing_name ?? c.nome ?? "Conta"])
  )
  const contasFiltradas = termo
    ? listaContas.filter((c) => contem(nomeConta.get(c.id), termo))
    : []
  const faturasFiltradas = termo
    ? (somenteDivisao ? [] : (faturas.data ?? []))
        .filter((f) =>
          contem(
            `fatura ${nomeConta.get(f.cartao_id) ?? ""} ${formatDate(f.due_date)}`,
            termo
          )
        )
        .slice(0, 5)
    : []
  // Enquanto a consulta do termo novo carrega, o TanStack mantém os itens do termo anterior
  // (placeholder): não oferecê-los, o `id` de um termo com a `busca` de outro não se acha.
  const itensTx =
    buscaTx && !transacoes.isPlaceholderData
      ? (transacoes.data?.items ?? []).filter((t) => !ehLancamento(t))
      : []

  return (
    <Command shouldFilter={false}>
      <CommandInput
        value={texto}
        onValueChange={setTexto}
        placeholder="Buscar transações, contas, páginas…"
      />
      <CommandList>
        <CommandEmpty>
          {buscaTx && transacoes.isFetching ? "Buscando…" : "Nada encontrado."}
        </CommandEmpty>
        {paginasFiltradas.length > 0 ? (
          <CommandGroup heading="Páginas">
            {paginasFiltradas.map((p) => (
              <CommandItem
                key={p.url}
                value={`p:${p.url}`}
                onSelect={() => ir(p.url)}
              >
                <p.icon aria-hidden />
                {p.title}
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
        {termo && abasFiltradas.length > 0 ? (
          <CommandGroup heading="Configurações">
            {abasFiltradas.map(([id, rotulo]) => (
              <CommandItem
                key={id}
                value={`c:${id}`}
                onSelect={() => ir(`/configuracoes?aba=${id}`)}
              >
                <Settings aria-hidden />
                {rotulo}
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
        {contasFiltradas.length > 0 ? (
          <CommandGroup heading="Contas e cartões">
            {contasFiltradas.map((c) => (
              <CommandItem
                key={c.id}
                value={`a:${c.id}`}
                onSelect={() => ir(`/contas/${c.id}`)}
              >
                {c.type === "CREDIT" ? (
                  <CreditCard aria-hidden />
                ) : (
                  <Landmark aria-hidden />
                )}
                {nomeConta.get(c.id)}
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
        {faturasFiltradas.length > 0 ? (
          <CommandGroup heading="Faturas">
            {faturasFiltradas.map((f) => (
              <CommandItem
                key={f.id}
                value={`f:${f.id}`}
                onSelect={() => ir(`/faturas/${f.id}`)}
              >
                <CreditCard aria-hidden />
                {nomeConta.get(f.cartao_id) ?? "Cartão"} · venc.{" "}
                {formatDate(f.due_date)}
                <Valor
                  centavos={-f.total_amount_centavos}
                  className="ml-auto shrink-0 text-xs whitespace-nowrap"
                />
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
        {itensTx.length > 0 ? (
          <CommandGroup heading="Transações">
            {itensTx.map((t) => {
              const desc = descricaoExibida(t) ?? "Transação"
              return (
                <CommandItem
                  key={t.id}
                  value={`t:${t.id}`}
                  onSelect={() =>
                    ir(
                      `/transacoes?busca=${encodeURIComponent(termoServidor)}&id=${t.id}`
                    )
                  }
                >
                  <ArrowRightLeft aria-hidden />
                  <span className="truncate">{desc}</span>
                  <span className="ml-auto flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    {formatDate(t.date)}
                    <Valor centavos={valorEfetivoCentavos(t)} sinal neutro />
                  </span>
                </CommandItem>
              )
            })}
            <CommandItem
              value="t:todas"
              onSelect={() =>
                ir(`/transacoes?busca=${encodeURIComponent(termoServidor)}`)
              }
            >
              <Search aria-hidden />
              Ver todas as transações com “{termoServidor}”
            </CommandItem>
          </CommandGroup>
        ) : null}
      </CommandList>
    </Command>
  )
}
