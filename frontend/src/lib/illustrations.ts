/** Ilustrações do mascote (DESIGN.md §Illustrations). Único resolvedor de caminho —
 * nunca hardcodar `avatar_1` em componente: a pasta vem do avatar escolhido pelo usuário. */

export const CENAS = [
  "default",
  "goal",
  "money",
  "money-v2",
  "subscriptions",
  "scared",
  "super-scared",
  "thumbs-up",
  "hang-loose",
  "surf",
  "mango-juice",
  "bar-scene",
] as const

export type Cena = (typeof CENAS)[number]

/** Avatares com assets em public/illustrations/avatars/. Atualizar quando 2–4 chegarem. */
export const AVATARES_DISPONIVEIS = [1]

export const AVATAR_PADRAO = 1

export function ilustracao(
  avatar: number | null | undefined,
  cena: Cena
): string {
  const n = avatar ?? AVATAR_PADRAO
  return `/illustrations/avatars/avatar_${n}/avatar-${n}-${cena}.png`
}
