import { useQueryClient } from "@tanstack/react-query"
import {
  Check,
  ChevronRight,
  LogOut,
  MoreHorizontal,
  Moon,
  Sun,
  X,
} from "lucide-react"
import { useState } from "react"
import { createPortal } from "react-dom"
import { NavLink, useLocation, useNavigate } from "react-router"

import { useTheme } from "@/components/theme-provider"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerTitle,
} from "@/components/ui/drawer"
import { Separator } from "@/components/ui/separator"
import {
  bottomNavItems,
  bottomNavItemsDivisaoOnly,
  investimentosSection,
  isActivePath,
  isBottomNavItemActive,
  navSections,
  navSectionsDivisaoOnly,
  settingsItem,
  type BottomNavItem,
  type NavItem,
  type NavSection,
} from "@/config/nav"
import { authKeys, useMe, useSetupStatus } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import { cn } from "@/lib/utils"

/** Mesmas opções do menu de usuário da sidebar: "Sistema" fica de fora (decisão de produto). */
const THEME_OPTIONS = [
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
] as const

/** Folga do rodapé: home indicator do iOS (o `index.html` já usa `viewport-fit=cover`). */
const SAFE_AREA_BOTTOM = "env(safe-area-inset-bottom)"

/** Linha recolhida do "Mais": ícone + título + descrição + chevron. */
const LINHA = "flex w-full items-center gap-3 px-4 py-3 text-left"
/** Subitem de uma seção expandida: recuado até alinhar com o texto da linha-mãe. */
const SUBLINHA =
  "flex w-full items-center gap-3 py-2.5 pr-4 pl-12 text-left text-sm"
/** Chevron que aponta para cima quando a seção está aberta. */
const CHEVRON =
  "size-4 shrink-0 text-muted-foreground transition-transform duration-200 motion-reduce:transition-none"
/**
 * Abre/fecha em altura (keyframes `collapsible-*` do tw-animate-css, sobre a var de altura que o
 * Radix mede). `overflow-hidden` é o que faz a lista ser revelada em vez de aparecer inteira.
 * `motion-safe:` e não `motion-reduce:animate-none` — o seletor `[data-state]` tem especificidade
 * maior e venceria o desligamento, deixando a animação de pé em quem pediu movimento reduzido.
 */
const CONTEUDO =
  "overflow-hidden motion-safe:data-[state=closed]:animate-collapsible-up motion-safe:data-[state=open]:animate-collapsible-down"

/** "Visão Geral e Carteira" — descrição derivada dos filhos, sem copy inventada por seção. */
function listar(titulos: string[]): string {
  if (titulos.length < 2) return titulos.join("")
  return `${titulos.slice(0, -1).join(", ")} e ${titulos[titulos.length - 1]}`
}

function TituloLinha({
  titulo,
  descricao,
  ativo,
}: {
  titulo: string
  descricao?: string
  ativo?: boolean
}) {
  return (
    <span className="grid flex-1 gap-1">
      <span
        className={cn(
          "text-sm leading-none font-medium",
          ativo && "text-primary"
        )}
      >
        {titulo}
      </span>
      {descricao ? (
        <span className="text-xs leading-none text-muted-foreground">
          {descricao}
        </span>
      ) : null}
    </span>
  )
}

/** Destino direto (sem filhos): navega e fecha o drawer. */
function LinhaLink({
  item,
  pathname,
  onNavegar,
}: {
  item: NavItem
  pathname: string
  onNavegar: () => void
}) {
  const ativo = isActivePath(pathname, item.url)
  return (
    <li>
      <NavLink to={item.url} onClick={onNavegar} className={LINHA}>
        <item.icon
          className={cn(
            "size-5 shrink-0",
            ativo ? "text-primary" : "text-muted-foreground"
          )}
          aria-hidden
        />
        <TituloLinha
          titulo={item.title}
          descricao={item.descricao}
          ativo={ativo}
        />
        <ChevronRight className={CHEVRON} aria-hidden />
      </NavLink>
    </li>
  )
}

/** Menu principal recolhido: abre para revelar os subitens (mesma IA da sidebar). */
function LinhaSecao({
  secao,
  pathname,
  onNavegar,
}: {
  secao: NavSection
  pathname: string
  onNavegar: () => void
}) {
  const temFilhoAtivo = secao.items.some((item) =>
    isActivePath(pathname, item.url)
  )
  return (
    <li>
      <Collapsible defaultOpen={temFilhoAtivo} className="group/secao">
        <CollapsibleTrigger className={LINHA}>
          <secao.icon
            className={cn(
              "size-5 shrink-0",
              temFilhoAtivo ? "text-primary" : "text-muted-foreground"
            )}
            aria-hidden
          />
          <TituloLinha
            titulo={secao.label}
            descricao={listar(secao.items.map((item) => item.title))}
            ativo={temFilhoAtivo}
          />
          <ChevronRight
            className={cn(CHEVRON, "group-data-[state=open]/secao:-rotate-90")}
            aria-hidden
          />
        </CollapsibleTrigger>
        <CollapsibleContent className={CONTEUDO}>
          <ul className="pb-1">
            {secao.items.map((item) => {
              const ativo = isActivePath(pathname, item.url)
              return (
                <li key={item.url}>
                  <NavLink
                    to={item.url}
                    onClick={onNavegar}
                    className={cn(
                      SUBLINHA,
                      ativo
                        ? "font-medium text-primary"
                        : "text-muted-foreground"
                    )}
                  >
                    <item.icon className="size-4 shrink-0" aria-hidden />
                    <span>{item.title}</span>
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}

/** Aba "Mais": drawer inferior com a IA completa recolhida, tema e logout. */
function AbaMais({ somenteDivisao }: { somenteDivisao: boolean }) {
  const [aberto, setAberto] = useState(false)
  const { pathname } = useLocation()
  const { theme, setTheme } = useTheme()
  const status = useSetupStatus()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const podeSair = status.data?.app_mode === "self_hosted"
  const secoes = somenteDivisao
    ? navSectionsDivisaoOnly
    : [...navSections, investimentosSection]
  // "Sistema" não é oferecido no menu, mas o valor persistido pode ser ele.
  const temaAtual = THEME_OPTIONS.find((opt) => opt.value === theme)
  const TemaIcon = temaAtual?.icon ?? Sun

  const fechar = () => setAberto(false)

  async function sair() {
    fechar()
    await api.POST("/api/auth/logout")
    await queryClient.invalidateQueries({ queryKey: authKeys.me })
    navigate("/login", { replace: true })
  }

  return (
    <>
      <li className="flex max-w-24 flex-1">
        <button
          type="button"
          onClick={() => setAberto(true)}
          aria-haspopup="dialog"
          aria-expanded={aberto}
          className={cn(
            "flex w-full flex-col items-center justify-center gap-1 transition-colors duration-150 motion-reduce:transition-none",
            aberto ? "font-medium text-primary" : "text-muted-foreground"
          )}
        >
          {/* A aba "Mais" alterna um painel em vez de navegar: o chip marca "aberto". */}
          <span
            className={cn(
              "flex size-8 items-center justify-center rounded-full transition-colors duration-150 motion-reduce:transition-none",
              aberto && "bg-primary/10"
            )}
          >
            <MoreHorizontal className="size-6" aria-hidden />
          </span>
          <span className="text-[11px] leading-none">Mais</span>
        </button>
      </li>

      <Drawer open={aberto} onOpenChange={setAberto}>
        {/* Altura fixa: expandir uma seção rola a lista em vez de crescer/encolher o drawer. */}
        <DrawerContent
          className="h-[80svh] md:hidden"
          style={{ paddingBottom: SAFE_AREA_BOTTOM }}
        >
          <div className="flex shrink-0 items-center justify-between px-4 pt-2 pb-3">
            <DrawerTitle className="text-base font-semibold">Mais</DrawerTitle>
            <DrawerClose className="-mr-1 rounded-md p-1 text-muted-foreground">
              <X className="size-5" aria-hidden />
              <span className="sr-only">Fechar</span>
            </DrawerClose>
          </div>
          <DrawerDescription className="sr-only">
            Navegação e preferências da conta.
          </DrawerDescription>
          <Separator className="shrink-0" />

          {/* min-h-0: sem isso o item flex não encolhe e a lista estoura a altura do drawer. */}
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <nav aria-label="Mais destinos">
              <ul>
                {secoes.map((secao) =>
                  // Seção de um item só não vale um nível de recolhimento.
                  secao.items.length === 1 ? (
                    <LinhaLink
                      key={secao.label}
                      item={secao.items[0]!}
                      pathname={pathname}
                      onNavegar={fechar}
                    />
                  ) : (
                    <LinhaSecao
                      key={secao.label}
                      secao={secao}
                      pathname={pathname}
                      onNavegar={fechar}
                    />
                  )
                )}
                <LinhaLink
                  item={settingsItem}
                  pathname={pathname}
                  onNavegar={fechar}
                />
              </ul>
            </nav>

            <Separator />

            <Collapsible className="group/tema">
              <CollapsibleTrigger className={LINHA}>
                <TemaIcon
                  className="size-5 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <TituloLinha
                  titulo="Tema"
                  descricao={temaAtual?.label ?? "Sistema"}
                />
                <ChevronRight
                  className={cn(
                    CHEVRON,
                    "group-data-[state=open]/tema:-rotate-90"
                  )}
                  aria-hidden
                />
              </CollapsibleTrigger>
              <CollapsibleContent className={CONTEUDO}>
                <ul className="pb-1">
                  {THEME_OPTIONS.map((opt) => (
                    <li key={opt.value}>
                      <button
                        type="button"
                        onClick={() => setTheme(opt.value)}
                        className={cn(
                          SUBLINHA,
                          theme === opt.value
                            ? "font-medium text-primary"
                            : "text-muted-foreground"
                        )}
                      >
                        <opt.icon className="size-4 shrink-0" aria-hidden />
                        <span className="flex-1">{opt.label}</span>
                        <Check
                          className={cn(
                            "size-4",
                            theme === opt.value ? "opacity-100" : "opacity-0"
                          )}
                          aria-hidden
                        />
                      </button>
                    </li>
                  ))}
                </ul>
              </CollapsibleContent>
            </Collapsible>

            {podeSair ? (
              <button
                type="button"
                onClick={sair}
                className={cn(LINHA, "text-destructive")}
              >
                <LogOut className="size-5 shrink-0" aria-hidden />
                <span className="grid flex-1 gap-1">
                  <span className="text-sm leading-none font-medium">Sair</span>
                  <span className="text-xs leading-none opacity-80">
                    Encerrar sessão
                  </span>
                </span>
              </button>
            ) : null}
          </div>
        </DrawerContent>
      </Drawer>
    </>
  )
}

function AbaLink({
  item,
  pathname,
}: {
  item: BottomNavItem
  pathname: string
}) {
  const ativa = isBottomNavItemActive(pathname, item)
  return (
    <li className="flex max-w-24 flex-1">
      <NavLink
        to={item.url}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-1 transition-colors duration-150 motion-reduce:transition-none",
          ativa ? "font-medium text-primary" : "text-muted-foreground"
        )}
      >
        {/* size-8 igual ao chip da aba "Mais": mantém todas as abas na mesma linha de base. */}
        <span className="flex size-8 items-center justify-center">
          <item.icon className="size-6" aria-hidden />
        </span>
        <span className="text-[11px] leading-none">{item.short}</span>
      </NavLink>
    </li>
  )
}

/**
 * Navegação inferior do mobile (`< md`): abas fixas + "Mais". Escondida por CSS, não por
 * `useIsMobile()` — o hook começa `false` e piscaria a barra no primeiro paint do desktop.
 *
 * Vai num portal para o `body`, como todo `fixed` do shadcn aqui (sheet, dialog, drawer): dentro
 * do `SidebarInset` bastaria um ancestral ganhar `transform`/`filter`/`backdrop-filter` para virar
 * o containing block e a barra passar a rolar com o conteúdo em vez de ficar presa à viewport.
 */
export function BottomNav() {
  const { pathname } = useLocation()
  const me = useMe()
  const somenteDivisao = me.data?.tipo === "divisao"
  const abas = somenteDivisao ? bottomNavItemsDivisaoOnly : bottomNavItems

  return createPortal(
    <nav
      aria-label="Navegação principal"
      className="fixed inset-x-0 bottom-0 z-40 border-t bg-background md:hidden"
      style={{ paddingBottom: SAFE_AREA_BOTTOM }}
    >
      <ul className="flex h-(--bottom-nav-h) items-stretch justify-around">
        {abas.map((item) => (
          <AbaLink key={item.url} item={item} pathname={pathname} />
        ))}
        <AbaMais somenteDivisao={somenteDivisao} />
      </ul>
    </nav>,
    document.body
  )
}
