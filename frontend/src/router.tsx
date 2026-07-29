import { createBrowserRouter, Navigate } from "react-router"

import { RequireAuth } from "@/components/auth/require-auth"
import { AppLayout } from "@/components/layout/app-layout"
import { AssinaturasPage } from "@/routes/assinaturas/page"
import { ConfiguracoesPage } from "@/routes/configuracoes/page"
import { ContaDetalhePage } from "@/routes/contas/detalhe"
import { ContasPage } from "@/routes/contas/page"
import { DashboardPage } from "@/routes/dashboard/page"
import { DivisoesPage } from "@/routes/divisoes/page"
import { FaturaDetalhePage } from "@/routes/faturas/detalhe"
import { FaturasPage } from "@/routes/faturas/page"
import { FontesDeRendaPage } from "@/routes/fontes-de-renda/page"
import { CarteiraPage } from "@/routes/investimentos/carteira"
import { InvestimentosPage } from "@/routes/investimentos/page"
import { VisaoGeralPage } from "@/routes/investimentos/visao-geral"
import { LoginPage } from "@/routes/login/page"
import { NotFoundPage } from "@/routes/not-found"
import { ObjetivosPage } from "@/routes/objetivos/page"
import { OrcamentosPage } from "@/routes/orcamentos/page"
import { SetupPage } from "@/routes/setup/page"
import { TransacoesPage } from "@/routes/transacoes/page"

// `/setup` e `/login` ficam FORA do app shell (sem sidebar). O `RequireAuth` guarda o restante:
// sem instância configurada → /setup; sem sessão (self-hosted) → /login. Ver require-auth.tsx.
// O `handle.title` de cada rota alimenta o breadcrumb do header (ver app-header.tsx).
export const router = createBrowserRouter([
  { path: "/setup", element: <SetupPage /> },
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          {
            index: true,
            element: <DashboardPage />,
            handle: { title: "Dashboard" },
          },
          {
            path: "transacoes",
            element: <TransacoesPage />,
            handle: { title: "Transações" },
          },
          {
            path: "contas",
            handle: { title: "Contas" },
            children: [
              { index: true, element: <ContasPage /> },
              {
                path: ":contaId",
                element: <ContaDetalhePage />,
                handle: { title: "Detalhe da conta" },
              },
            ],
          },
          {
            path: "faturas",
            handle: { title: "Faturas" },
            children: [
              { index: true, element: <FaturasPage /> },
              {
                path: ":faturaId",
                element: <FaturaDetalhePage />,
                handle: { title: "Detalhe da fatura" },
              },
            ],
          },
          {
            path: "orcamentos",
            element: <OrcamentosPage />,
            handle: { title: "Orçamentos" },
          },
          {
            path: "objetivos",
            element: <ObjetivosPage />,
            handle: { title: "Objetivos" },
          },
          {
            path: "investimentos",
            handle: { title: "Investimentos" },
            children: [
              { index: true, element: <Navigate to="visao_geral" replace /> },
              {
                path: "visao_geral",
                element: <VisaoGeralPage />,
                handle: { title: "Visão Geral" },
              },
              {
                path: "carteira",
                element: <CarteiraPage />,
                handle: { title: "Carteira" },
              },
              // Backup temporário da Carteira antiga enquanto validamos o novo design.
              {
                path: "carteira-legado",
                element: <InvestimentosPage />,
                handle: { title: "Carteira (legado)" },
              },
            ],
          },
          {
            path: "assinaturas",
            element: <AssinaturasPage />,
            handle: { title: "Assinaturas" },
          },
          {
            path: "divisoes",
            element: <DivisoesPage />,
            handle: { title: "Divisão de contas" },
          },
          {
            path: "fontes-de-renda",
            element: <FontesDeRendaPage />,
            handle: { title: "Fontes de renda" },
          },
          {
            path: "configuracoes",
            element: <ConfiguracoesPage />,
            handle: { title: "Configurações" },
          },
          {
            path: "*",
            element: <NotFoundPage />,
            handle: { title: "Não encontrado" },
          },
        ],
      },
    ],
  },
])
