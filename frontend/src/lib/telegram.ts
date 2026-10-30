export type TelegramWebApp = {
  initData: string
  ready: () => void
  expand: () => void
  enableClosingConfirmation: () => void
  disableClosingConfirmation: () => void
}
declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp }
  }
}
let carregamento: Promise<TelegramWebApp> | undefined
export function carregarTelegram(): Promise<TelegramWebApp> {
  if (window.Telegram?.WebApp) return Promise.resolve(window.Telegram.WebApp)
  return (carregamento ??= new Promise((resolve, reject) => {
    const script = document.createElement("script")
    script.src = "https://telegram.org/js/telegram-web-app.js"
    script.onload = () =>
      window.Telegram?.WebApp
        ? resolve(window.Telegram.WebApp)
        : reject(new Error("Telegram indisponível"))
    script.onerror = () => {
      carregamento = undefined
      script.remove()
      reject(new Error("Não foi possível carregar o Telegram"))
    }
    document.head.append(script)
  }))
}
