import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

// Sin role fijo: el aviso fijo y el de cobertura no son alertas. Quien lo use pone
// role="alert" solo en errores que deben anunciarse (inicio de sesión, documentos).
// Íconos de 20 px como los de Iconos.tsx; la variante refuerza con color y borde, nunca sola.
const alertVariants = cva(
  "group/alert relative grid w-full gap-1 rounded-lg border px-4 py-3 text-left text-base has-[>svg]:grid-cols-[auto_1fr] has-[>svg]:gap-x-2 *:[svg]:row-span-2 *:[svg]:mt-0.5 *:[svg]:text-current *:[svg:not([class*='size-'])]:size-5",
  {
    variants: {
      variant: {
        default: "border-border bg-card text-card-foreground",
        neutro: "border-y-0 border-r-0 border-l-4 border-input bg-muted text-foreground",
        revision: "border-y-0 border-r-0 border-l-4 border-estado-revision bg-estado-revision-fondo text-foreground",
        destructive: "border-2 border-destructive bg-destructive-fondo text-foreground *:data-[slot=alert-title]:text-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      data-variant={variant ?? "default"}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  )
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "leading-titulo font-semibold group-has-[>svg]/alert:col-start-2",
        className
      )}
      {...props}
    />
  )
}

function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn("min-w-0 wrap-anywhere group-has-[>svg]/alert:col-start-2 text-pretty [&_p:not(:last-child)]:mb-2", className)}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription }
