import { Button } from "@/components/ui/button"
import { DialogClose, DialogFooter } from "@/components/ui/dialog"

/** Rodapé "Cancelar / <ação>" dos diálogos de formulário.
 *
 * Os diálogos de categoria e de regra tinham o mesmo bloco literal — só mudava o rótulo do botão
 * de submissão e a condição de habilitá-lo. Uma cópia a mais é onde nasce a divergência de
 * comportamento (um fecha ao cancelar, o outro não).
 */
export function RodapeDialogoForm({
  acao,
  desabilitado = false,
}: {
  /** Rótulo do botão de submissão ("Criar", "Salvar"). */
  acao: string
  desabilitado?: boolean
}) {
  return (
    <DialogFooter>
      <DialogClose asChild>
        <Button type="button" variant="outline">
          Cancelar
        </Button>
      </DialogClose>
      <Button type="submit" disabled={desabilitado}>
        {acao}
      </Button>
    </DialogFooter>
  )
}
