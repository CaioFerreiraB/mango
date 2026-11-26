/**
 * Botão redondo da topbar do celular (proposta C): círculo na cor do accent com o ícone na cor
 * de texto do preset (branco; tinta escura nas cores vivas, onde branco não leria). Sempre com
 * fundo — no topo e depois de rolar. Só abaixo de `md`: no desktop o botão segue o próprio estilo.
 */
export const BOTAO_TOPO_MOBILE =
  "max-md:size-10 max-md:rounded-full max-md:bg-marca-forte max-md:text-primary-foreground max-md:hover:bg-[color-mix(in_oklab,var(--marca-forte),black_10%)] max-md:hover:text-primary-foreground max-md:[&_svg]:size-5"
