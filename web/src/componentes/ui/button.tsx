import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

// Ajustado a DISENO.md: alto mínimo de 44 px, el foco lo pone la capa base (sin outline-none),
// deshabilitado con opacidad y cursor not-allowed (sin pointer-events-none) y texto que puede
// partirse para no desbordar a 320 px.
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border text-center text-base font-semibold leading-titulo transition-colors select-none motion-safe:active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-5",
  {
    variants: {
      variant: {
        default:
          "border-primary bg-primary text-primary-foreground hover:not-disabled:border-primary-hover hover:not-disabled:bg-primary-hover active:not-disabled:bg-primary-active",
        outline:
          "border-input bg-transparent text-foreground hover:not-disabled:bg-muted-hover active:not-disabled:bg-muted-active",
        ghost:
          "border-transparent bg-transparent text-foreground hover:not-disabled:bg-muted-hover active:not-disabled:bg-muted-active",
        link: "border-transparent text-primary underline underline-offset-2 hover:decoration-2",
      },
      size: {
        default: "min-h-11 px-6 py-2",
        sm: "min-h-11 px-4 py-2",
        icon: "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
