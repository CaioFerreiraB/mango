// Serve the existing frontend without environment files or a backend proxy.
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const frontend = fileURLToPath(new URL('../frontend/', import.meta.url));
const requireFrontend = createRequire(new URL('../frontend/package.json', import.meta.url));
const { createServer, loadConfigFromFile } = await import(pathToFileURL(requireFrontend.resolve('vite')).href);
const loaded = await loadConfigFromFile(
  { command: 'serve', mode: 'development' },
  path.join(frontend, 'vite.config.ts'),
  frontend,
);
if (!loaded) throw new Error('Não foi possível carregar a configuração do frontend.');

const server = await createServer({
  ...loaded.config,
  configFile: false,
  root: frontend,
  envDir: false,
  envPrefix: [],
  define: { ...loaded.config.define, 'import.meta.env.VITE_API_BASE_URL': '""' },
  server: {
    ...loaded.config.server,
    proxy: undefined,
    host: '127.0.0.1',
    port: 5177,
    strictPort: true,
  },
});
await server.listen();
server.printUrls();

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, async () => {
    await server.close();
    process.exit(0);
  });
}
