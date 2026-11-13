/** Capture the unmodified mango frontend using fictional, in-memory API fixtures only.
 * Start isolated frontend: node brag-output/serve-demo.mjs
 * Then: node brag-output/capture-demo.mjs
 * No backend, environment file, saved browser profile, or financial database is read.
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

let playwright;
try {
  playwright = await import('playwright');
} catch (error) {
  if (!process.env.PLAYWRIGHT_MODULE) throw new Error('Install brag-output dependencies or set PLAYWRIGHT_MODULE to an installed playwright/index.mjs.', { cause: error });
  playwright = await import(process.env.PLAYWRIGHT_MODULE);
}
const { chromium } = playwright;

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const destination = path.join(root, 'brag-output/composition/assets/screens');
const origin = 'http://127.0.0.1:5177';
const schema = JSON.parse(await readFile(path.join(root, 'frontend/openapi.json'), 'utf8'));
const now = '2026-10-23T15:00:00.000Z';

// Include nulls for nullable columns, including required nullable response properties.
function record(name, values) {
  const properties = schema.components.schemas[name].properties;
  const nullable = Object.fromEntries(Object.entries(properties)
    .filter(([, v]) => v.anyOf?.some((type) => type.type === 'null'))
    .map(([key]) => [key, null]));
  const result = { ...nullable, ...values };
  for (const key of schema.components.schemas[name].required ?? []) {
    if (!(key in result)) throw new Error(`Missing fixture property ${name}.${key}`);
  }
  return result;
}

const me = record('MeRead', {
  id: 1, nome: 'Alex', email: 'alex@example.invalid', accent: 'violeta', avatar: 1,
  tipo: 'completo', is_admin: true, totp_configurado: true, totp_login_habilitado: true,
});
const profile = record('PerfilRead', {
  ...me, salario_mensal_centavos: 850000, revisao_desde: '2026-10-01',
  brapi_token_configurado: false,
});
const categoryDefinitions = [
  ['moradia', 'Moradia', 'home', 220000, 250000],
  ['alimentacao', 'Alimentação', 'shopping-cart', 118000, 160000],
  ['transporte', 'Transporte', 'car', 42000, 60000],
  ['lazer', 'Lazer', 'gamepad-2', 72000, 100000],
  ['saude', 'Saúde', 'heart-pulse', 36000, 50000],
  ['assinaturas', 'Assinaturas', 'monitor-smartphone', 44000, 60000],
  ['salario', 'Salário', 'briefcase', 850000, 850000],
];
const categories = categoryDefinitions.map(([id, name, icon]) => record('CategoriaRead', {
  pluggy_id: id, description: name, description_translated: name, icone: icon,
  personalizada: true, ativa: true,
}));
const accounts = [
  [1, 'Conta principal', 'BANK', 1268000],
  [2, 'Cartão do dia a dia', 'CREDIT', 0],
  [3, 'Reserva de emergência', 'BANK', 1800000],
].map(([id, name, type, balance]) => record('ContaRead', {
  id, usuario_id: 1, item_id: 1, instituicao_id: 1,
  pluggy_account_id: `demo-account-${id}`, type, subtype: type === 'BANK' ? 'CHECKING_ACCOUNT' : null,
  nome: name, marketing_name: name, owner: 'Alex', saldo_centavos: balance, currency_code: 'BRL',
}));

// Fictional entries add up to R$ 8,500 income and R$ 5,320 spending.
const transactions = [
  [101, 23, 'Mercado da Praça', -28690, 'alimentacao', false, 2],
  [102, 22, 'Cinema com amigos', -9600, 'lazer', false, 2],
  [103, 21, 'Transporte urbano', -8400, 'transporte', false, 1],
  [104, 20, 'Livraria Horizonte', -18400, 'lazer', true, 2],
  [105, 19, 'Farmácia do Bairro', -12000, 'saude', true, 2],
  [106, 17, 'Mercado da Praça', -34510, 'alimentacao', true, 2],
  [107, 15, 'Internet e serviços', -44000, 'assinaturas', true, 1],
  [108, 14, 'Passeio de fim de semana', -44000, 'lazer', true, 2],
  [109, 12, 'Consulta de rotina', -24000, 'saude', true, 1],
  [110, 10, 'Mobilidade', -33600, 'transporte', true, 1],
  [111, 9, 'Feira e supermercado', -54800, 'alimentacao', true, 2],
  [112, 7, 'Aluguel e condomínio', -220000, 'moradia', true, 1],
  [113, 5, 'Salário de outubro', 850000, 'salario', true, 1],
].map(([id, day, description, amount, category, reviewed, account]) => record('TransacaoRead', {
  id, conta_id: account, pluggy_transaction_id: `demo-transaction-${id}`,
  date: `2026-10-${String(day).padStart(2, '0')}T12:00:00-03:00`, description,
  amount_centavos: amount, currency_code: 'BRL', type: amount < 0 ? 'DEBIT' : 'CREDIT',
  status: 'POSTED', categoria_pluggy_id: category, categoria_efetiva_id: category,
  categoria_ajustada_usuario: false, categoria_origem: 'banco', eh_transferencia: false,
  revisada: reviewed, nao_e_assinatura: false, usuario_id: 1,
  criado_em: now, atualizado_em: now, parcelas_atualizadas: 0,
}));
const incomeTotal = transactions.filter((t) => t.amount_centavos > 0).reduce((sum, t) => sum + t.amount_centavos, 0);
const expenseTotal = transactions.filter((t) => t.amount_centavos < 0).reduce((sum, t) => sum - t.amount_centavos, 0);
if (incomeTotal !== 850000 || expenseTotal !== 532000 || incomeTotal - expenseTotal !== 318000) {
  throw new Error('Fictional transaction totals do not match the presentation.');
}
const spending = categoryDefinitions.slice(0, 6).map(([id, , , total]) => ({ categoria_id: id, total_centavos: total }));
const budget = record('OrcamentoConsumoRead', {
  ano: 2026, mes: 10,
  itens: categoryDefinitions.map(([id, , , actual, limit], i) => record('OrcamentoConsumoItem', {
    orcamento_id: i + 1, orcamento_mensal_id: i + 101, categoria_id: id,
    tipo: id === 'salario' ? 'receita' : 'despesa', recorrente: true, suprimido: false,
    limite_centavos: limit, realizado_centavos: actual, percentual: Math.round(actual / limit * 100),
    alerta_atingido: id === 'salario' ? null : [100, 90, 75, 50].find((n) => actual / limit * 100 >= n) ?? null,
  })),
});
const goals = [
  [1, 'Reserva de emergência', 'Tranquilidade para os imprevistos.', 3000000, 1800000],
  [2, 'Próxima viagem', 'Um plano que ganha forma a cada mês.', 1200000, 780000],
  [3, 'Novo espaço de trabalho', 'Mais conforto para trabalhar e criar.', 800000, 320000],
].map(([id, title, description, target, saved]) => record('ObjetivoRead', {
  id, usuario_id: 1, titulo: title, descricao: description, justificativa: null,
  valor_alvo_centavos: target, valor_guardado_centavos: saved, progresso: saved / target,
  criado_em: now, atualizado_em: now,
}));

function dashboard(previous = false) {
  return record('DashboardResumo', {
    saldo_total_centavos: 3068000, entradas_centavos: previous ? 810000 : 850000,
    saidas_centavos: previous ? 579000 : 532000, resultado_centavos: previous ? 231000 : 318000,
    nao_revisadas: transactions.filter((t) => !t.revisada).length,
    gasto_por_categoria: spending, ultimas_transacoes: transactions.slice(0, 5), faturas_abertas: [],
  });
}
function series(url) {
  const granularity = url.searchParams.get('granularidade');
  const start = url.searchParams.get('inicio');
  if (start < '2026-10-01') {
    return { buckets: [
      [4, 780000, 603000], [5, 805000, 588000], [6, 810000, 621000],
      [7, 800000, 580000], [8, 820000, 601000], [9, 810000, 579000],
    ].map(([month, income, expense]) => ({ inicio: `2026-${String(month).padStart(2, '0')}-01`, entradas_centavos: income,
      saidas_centavos: expense, resultado_centavos: income - expense, por_categoria: [] })) };
  }
  const groups = new Map();
  for (let day = 1; day <= 23; day++) {
    const group = granularity === 'mensal' ? 1 : granularity === 'semanal' ? 1 + Math.floor((day - 1) / 7) * 7 : day;
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(...transactions.filter((t) => Number(t.date.slice(8, 10)) === day));
  }
  return { buckets: [...groups].map(([day, entries]) => {
    const income = entries.filter((t) => t.type === 'CREDIT').reduce((total, t) => total + t.amount_centavos, 0);
    const expense = entries.filter((t) => t.type === 'DEBIT').reduce((total, t) => total - t.amount_centavos, 0);
    return { inicio: `2026-10-${String(day).padStart(2, '0')}`, entradas_centavos: income, saidas_centavos: expense,
      resultado_centavos: income - expense, por_categoria: categoryDefinitions.slice(0, 6).map(([id]) => ({
        categoria_id: id, total_centavos: entries.filter((t) => t.categoria_efetiva_id === id).reduce((total, t) => total - t.amount_centavos, 0),
      })).filter((c) => c.total_centavos > 0) };
  }) };
}

const requested = new Set();
const unexpected = [];
let reviewMutation = null;
function apiResponse(url, request) {
  const route = url.pathname;
  requested.add(`${request.method()} ${route}`);
  if (route === '/api/setup/status') return { configured: true, app_mode: 'self_hosted' };
  if (route === '/api/auth/me') return me;
  if (route === '/api/perfil') return profile;
  if (route === '/api/contas') return accounts;
  if (route === '/api/categorias') return categories;
  if (route === '/api/assinaturas') return [];
  if (route === '/api/dashboard') return dashboard(url.searchParams.get('inicio') < '2026-10-01');
  if (route === '/api/dashboard/series') return series(url);
  if (route === '/api/orcamentos/consumo') return budget;
  if (route === '/api/orcamentos') return budget.itens.map((item, i) => record('OrcamentoRead', {
    id: item.orcamento_id, categoria_id: item.categoria_id, tipo: item.tipo,
    limite_padrao_centavos: item.limite_centavos, recorrente: true, ativo: true, ordem: i,
    usuario_id: 1, criado_em: now, atualizado_em: now,
  }));
  if (route === '/api/objetivos') return goals;
  if (route === '/api/transacoes') {
    const filtered = transactions.filter((t) => url.searchParams.get('pendente_revisao') !== 'true' || !t.revisada);
    return { items: filtered, total: filtered.length };
  }
  if (route === '/api/transacoes/101' && request.method() === 'PATCH') {
    const patch = request.postDataJSON();
    if (Object.keys(patch).length !== 1 || patch.revisada !== true) throw new Error('Unexpected mutation');
    Object.assign(transactions[0], patch);
    reviewMutation = { path: route, method: 'PATCH', body: patch };
    return transactions[0];
  }
  unexpected.push(`${request.method()} ${route}`);
  return undefined;
}

await mkdir(destination, { recursive: true });
const browser = await chromium.launch({ headless: true, args: ['--disable-dev-shm-usage'],
  ...(process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE } : {}),
});
try {
  const context = await browser.newContext({ viewport: { width: 1600, height: 960 }, deviceScaleFactor: 1,
    colorScheme: 'light', locale: 'pt-BR', timezoneId: 'America/Sao_Paulo', serviceWorkers: 'block' });
  await context.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/')) {
      const body = apiResponse(url, request);
      return route.fulfill({ status: body === undefined ? 501 : 200, contentType: 'application/json',
        body: JSON.stringify(body ?? { detail: 'No demo fixture for endpoint; real backend blocked.' }) });
    }
    if (url.origin === origin && request.method() === 'GET') return route.continue();
    unexpected.push(`BLOCKED ${request.method()} ${url.origin}${url.pathname}`);
    return route.abort('blockedbyclient');
  });
  await context.routeWebSocket('**/*', (socket) => socket.close());
  await context.addInitScript(() => {
    localStorage.setItem('theme', 'light');
    localStorage.setItem('accent', 'violeta');
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.clock.setFixedTime(new Date(now));
  async function settle() {
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(2000);
    if (unexpected.length || errors.length) throw new Error(JSON.stringify({ unexpected, errors }));
  }
  async function capture(name) {
    await settle();
    await page.screenshot({ path: path.join(destination, `${name}.png`), animations: 'disabled' });
  }
  await page.goto(origin, { waitUntil: 'networkidle' });
  await page.getByText('Este mês até hoje', { exact: true }).waitFor();
  await page.getByRole('radio', { name: 'Semanal', exact: true }).first().click();
  await capture('dashboard');
  await page.goto(`${origin}/transacoes`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'Mercado da Praça', exact: true }).first().waitFor();
  await capture('transacoes-before');
  const row = page.getByRole('button', { name: 'Mercado da Praça', exact: true }).first();
  const rowBox = await row.boundingBox();
  const rowClick = { x: Math.round(rowBox.x + rowBox.width / 2), y: Math.round(rowBox.y + rowBox.height / 2), box: rowBox };
  await row.click();
  const reviewSwitch = page.getByRole('switch', { name: 'Transação revisada', exact: true });
  await reviewSwitch.waitFor();
  await capture('transacoes-detail');
  const box = await reviewSwitch.boundingBox();
  const reviewClick = { x: Math.round(box.x + box.width / 2), y: Math.round(box.y + box.height / 2), box };
  await reviewSwitch.click();
  await page.waitForFunction(() => document.querySelector('[role="dialog"] [role="switch"]')?.getAttribute('aria-checked') === 'true');
  await capture('transacoes-after');
  await page.keyboard.press('Escape');
  await capture('transacoes-revisada');
  await page.goto(`${origin}/orcamentos`, { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: 'Orçamento', exact: true }).waitFor();
  await capture('orcamentos');
  await page.goto(`${origin}/objetivos`, { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: 'Objetivos', exact: true }).waitFor();
  await capture('objetivos');
  if (!reviewMutation) throw new Error('The review click did not issue a mutation.');
  const manifest = { width: 1600, height: 960, fictionalData: true, fixedDate: now,
    frontend: 'Unmodified existing mango frontend', rowClick, reviewClick, reviewMutation,
    requests: [...requested], unexpected, errors,
    screenshots: ['dashboard', 'transacoes-before', 'transacoes-detail', 'transacoes-after', 'transacoes-revisada', 'orcamentos', 'objetivos'],
  };
  await writeFile(path.join(destination, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(JSON.stringify(manifest, null, 2));
} finally {
  await browser.close();
}
