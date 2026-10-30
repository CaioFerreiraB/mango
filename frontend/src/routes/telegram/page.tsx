import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { Link, Outlet, useNavigate } from "react-router"
import { NovaDivisaoWizard } from "@/components/divisoes/nova-divisao-wizard"
import { Button } from "@/components/ui/button"
import { useMe } from "@/lib/api/auth"
import { api, sessaoMiniapp } from "@/lib/api/client"
import { mensagemErro } from "@/lib/api/erros"
import { carregarTelegram } from "@/lib/telegram"

export function MiniappLayout() {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, refetchOnWindowFocus: false },
          mutations: { retry: false },
        },
      })
  )
  const [estado, setEstado] = useState("carregando")
  useEffect(() => {
    let ativo = true
    let prazo: ReturnType<typeof setTimeout>
    async function iniciar() {
      try {
        const tg = await carregarTelegram()
        if (!tg.initData)
          throw new Error("Abra este miniapp pelo botão do bot no Telegram.")
        const { data, error } = await api.POST("/api/telegram/miniapp/sessao", {
          body: { init_data: tg.initData },
          credentials: "omit",
        })
        if (error || !data)
          throw new Error(
            mensagemErro(error, "Não foi possível abrir sua sessão.")
          )
        if (!ativo) return
        sessaoMiniapp(data.token)
        setEstado("pronto")
        tg.ready()
        tg.expand()
        prazo = setTimeout(
          () => {
            sessaoMiniapp(null)
            client.clear()
            setEstado("Sessão expirada. Feche e abra novamente pelo Telegram.")
          },
          Math.max(0, Date.parse(data.expira_em) - Date.now())
        )
      } catch (e) {
        if (ativo)
          setEstado(
            e instanceof Error ? e.message : "Falha ao abrir o miniapp."
          )
      }
    }
    void iniciar()
    return () => {
      ativo = false
      clearTimeout(prazo)
      sessaoMiniapp(null)
      client.clear()
    }
  }, [client])
  return (
    <QueryClientProvider client={client}>
      <div className="mx-auto min-h-dvh max-w-lg px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))]">
        <header className="mb-6 border-b pb-3">
          <Link className="text-lg font-semibold" to="/telegram">
            Mango
          </Link>
        </header>
        {estado === "pronto" ? (
          <Outlet />
        ) : (
          <p role="status">
            {estado === "carregando" ? "Abrindo sua sessão…" : estado}
          </p>
        )}
      </div>
    </QueryClientProvider>
  )
}

export function MiniappEntrada() {
  const me = useMe()
  const fila = useQuery({
    queryKey: ["revisao", "entrada"],
    enabled: me.data?.tipo === "completo",
    queryFn: async () => {
      const { data, error } = await api.GET("/api/revisao")
      if (error || !data)
        throw new Error("Não foi possível carregar as pendências.")
      return data
    },
  })
  return (
    <main className="space-y-6">
      <h1 className="text-xl font-semibold">
        Olá, {me.data?.nome ?? "bem-vindo"}
      </h1>
      {fila.isError ? (
        <p role="alert">
          {fila.error.message}{" "}
          <Button variant="outline" onClick={() => fila.refetch()}>
            Tentar novamente
          </Button>
        </p>
      ) : null}
      {fila.data && fila.data.total > 0 ? (
        <section className="space-y-3 rounded-xl border p-4">
          <h2 className="font-semibold">
            {fila.data.total} transações para revisar
          </h2>
          <Button asChild>
            <Link to="revisao">Revisar transações</Link>
          </Button>
        </section>
      ) : null}
      <section className="space-y-3">
        <h2 className="font-semibold">Divisão de contas</h2>
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <Link to="split">Nova divisão</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="divisoes">Ver divisões</Link>
          </Button>
        </div>
      </section>
    </main>
  )
}

export function MiniappSplit() {
  const navigate = useNavigate()
  return (
    <NovaDivisaoWizard
      initialOpen
      onClose={() => navigate("/telegram")}
      trigger={<Button>Nova divisão</Button>}
    />
  )
}
