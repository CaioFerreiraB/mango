import type { ComponentProps, ReactNode, RefObject } from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

export function ConfirmacaoTelegram({
  aberto,
  pendente,
  alterar,
  confirmar,
  foco,
  titulo,
  acao,
  children,
}: {
  aberto: boolean
  pendente: boolean
  alterar: NonNullable<ComponentProps<typeof AlertDialog>["onOpenChange"]>
  confirmar: () => void
  foco: RefObject<HTMLElement | null>
  titulo: string
  acao: string
  children: ReactNode
}) {
  return (
    <AlertDialog
      open={aberto}
      onOpenChange={(valor) => {
        if (!pendente) alterar(valor)
      }}
    >
      <AlertDialogContent
        onCloseAutoFocus={(e) => {
          e.preventDefault()
          foco.current?.focus()
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>{titulo}</AlertDialogTitle>
          <AlertDialogDescription>{children}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pendente}>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            disabled={pendente}
            onClick={(e) => {
              e.preventDefault()
              confirmar()
            }}
          >
            {acao}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
