import * as React from "react"
import { cn } from "cn"

// DISENO.md: el alto lo dan las filas (rows) y el analista puede agrandarla en vertical.
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "min-h-11 w-full min-w-0 resize-y rounded-lg border border-input bg-card px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
