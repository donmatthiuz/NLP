import * as React from "react"
import { cn } from "cn"
import { Label as LabelPrimitive } from "radix-ui"

// DISENO.md: rótulo visible en peso 600; atenuado y con cursor not-allowed si su control está deshabilitado.
function Label({
  className,
  ...props
}: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-base leading-titulo font-semibold select-none group-data-[disabled=true]:opacity-60 peer-disabled:cursor-not-allowed peer-disabled:opacity-60",
        className
      )}
      {...props}
    />
  )
}

export { Label }
