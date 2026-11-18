import * as React from "react"
import { cn } from "cn"
import { Checkbox as CheckboxPrimitive } from "radix-ui"
import { CheckIcon } from "lucide-react"

// Radix pinta un <button role="checkbox">, no un <input>, y marca el estado con data-state="checked". Caja de 20 px con zona de toque
// ampliada por ::after; el foco lo pone la capa base.
function Checkbox({
  className,
  ...props
}: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer relative flex size-5 shrink-0 items-center justify-center rounded-sm border border-input bg-card transition-colors after:absolute after:-inset-x-3 after:-inset-y-3 hover:not-disabled:bg-muted-hover disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-destructive data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground hover:not-disabled:data-[state=checked]:bg-primary-hover",
        className
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="grid place-content-center text-current transition-none [&>svg]:size-4"
      >
        <CheckIcon aria-hidden="true" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
