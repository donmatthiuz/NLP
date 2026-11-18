import * as React from "react"
import { cn } from "cn"
import { RadioGroup as RadioGroupPrimitive } from "radix-ui"

// Radix: cada opción es un <button role="radio"> con foco itinerante (flechas entre opciones).
// Para el rol lector, pasar disabled al RadioGroup además del fieldset deshabilitado.
function RadioGroup({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Root>) {
  return (
    <RadioGroupPrimitive.Root
      data-slot="radio-group"
      className={cn("grid w-full gap-2", className)}
      {...props}
    />
  )
}

function RadioGroupItem({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      data-slot="radio-group-item"
      className={cn(
        "peer relative flex aspect-square size-5 shrink-0 items-center justify-center rounded-full border border-input bg-card transition-colors after:absolute after:-inset-x-3 after:-inset-y-3 hover:not-disabled:bg-muted-hover disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-destructive data-[state=checked]:border-primary data-[state=checked]:bg-primary",
        className
      )}
      {...props}
    >
      <RadioGroupPrimitive.Indicator
        data-slot="radio-group-indicator"
        className="flex items-center justify-center"
      >
        <span className="size-2 rounded-full bg-primary-foreground" />
      </RadioGroupPrimitive.Indicator>
    </RadioGroupPrimitive.Item>
  )
}

export { RadioGroup, RadioGroupItem }
