import * as React from "react"
import { cn } from "../../lib/utils"

const Card = React.forwardRef(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-md bg-surface-lowest shadow-[var(--shadow-ambient)]",
      className
    )}
    {...props}
  >
    {children}
  </div>
))
Card.displayName = "Card"

export { Card }
