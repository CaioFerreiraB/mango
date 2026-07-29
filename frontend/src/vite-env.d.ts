/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origem da API. Vazio/ausente = mesma origem (dev usa o proxy do Vite; prod é servido junto). */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
