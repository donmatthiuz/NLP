import * as React from "react"
import { cn } from "cn"
import { CheckIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react"
import { Select as SelectPrimitive } from "radix-ui"

const Select = SelectPrimitive.Root
const SelectValue = SelectPrimitive.Value

function SelectTrigger({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      className={cn(
        "flex min-h-11 w-full min-w-0 items-center justify-between gap-3 rounded-lg border border-input bg-card px-3 py-2 text-left text-base text-foreground transition-colors duration-150 hover:not-disabled:bg-muted-hover disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-destructive [&>span]:min-w-0 [&>span]:wrap-anywhere",
        className
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  )
}

function SelectContent({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        data-slot="select-content"
        position="popper" sideOffset={6} align="start" collisionPadding={16}
        className={cn(
          "z-50 max-h-[var(--radix-select-content-available-height)] w-[var(--radix-select-trigger-width)] max-w-[var(--radix-select-content-available-width)] overflow-hidden rounded-lg border border-input bg-popover text-popover-foreground",
          className
        )}
        {...props}
      >
        <SelectPrimitive.ScrollUpButton className="flex min-h-11 items-center justify-center">
          <ChevronUpIcon className="size-4" aria-hidden="true" />
        </SelectPrimitive.ScrollUpButton>
        <SelectPrimitive.Viewport className="p-1">{children}</SelectPrimitive.Viewport>
        <SelectPrimitive.ScrollDownButton className="flex min-h-11 items-center justify-center">
          <ChevronDownIcon className="size-4" aria-hidden="true" />
        </SelectPrimitive.ScrollDownButton>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  )
}

function SelectItem({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        "relative flex min-h-11 cursor-pointer items-center rounded-md py-2 pr-9 pl-3 text-base wrap-anywhere select-none data-disabled:cursor-not-allowed data-disabled:opacity-60 data-highlighted:bg-muted-hover data-highlighted:text-accent-foreground data-[state=checked]:font-semibold",
        className
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator className="absolute right-3 flex items-center">
        <CheckIcon className="size-4" aria-hidden="true" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  )
}

export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue }
