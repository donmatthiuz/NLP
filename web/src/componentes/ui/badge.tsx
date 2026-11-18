import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

// Etiqueta de DISENO.md (.etiqueta): texto de 14 px (--texto-xs queda solo para contadores),
// borde de control y radio de control. No es pulsable.
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1 rounded-lg border px-2 py-1 text-sm leading-titulo font-semibold [&>svg]:pointer-events-none [&>svg]:size-4",
  {
    variants: {
      variant: {
        default: "border-input bg-muted text-foreground",
        aviso: "border-estado-revision bg-estado-revision-fondo text-estado-revision",
        suave: "border-input bg-muted font-normal text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
