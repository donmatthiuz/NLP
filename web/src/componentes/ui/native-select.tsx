import * as React from "react"
import { cn } from "cn"
import { ChevronDownIcon } from "lucide-react"

type NativeSelectProps = React.ComponentProps<"select">

// Selector nativo (tema y ejemplo): conserva el teclado y el lector del sistema. 44 px de alto.
function NativeSelect({ className, ...props }: NativeSelectProps) {
  return (
    <div
      className={cn(
        "group/native-select relative w-fit max-w-full has-[select:disabled]:opacity-60",
        className
      )}
      data-slot="native-select-wrapper"
    >
      <select
        data-slot="native-select"
        className="min-h-11 w-full min-w-0 appearance-none rounded-lg border border-input bg-card py-2 pr-9 pl-3 text-base text-foreground transition-colors hover:not-disabled:bg-muted-hover disabled:cursor-not-allowed aria-invalid:border-destructive"
        {...props}
      />
      <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground select-none" aria-hidden="true" data-slot="native-select-icon" />
    </div>
  )
}

function NativeSelectOption({
  className,
  ...props
}: React.ComponentProps<"option">) {
  return (
    <option
      data-slot="native-select-option"
      className={cn("bg-[Canvas] text-[CanvasText]", className)}
      {...props}
    />
  )
}

export { NativeSelect, NativeSelectOption }
