import * as React from "react"
import { cn } from "../../lib/utils"

const Button = React.forwardRef(({ className, variant = "primary", size = "default", ...props }, ref) => {
  const baseStyles = "inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-all duration-400 ease-[cubic-bezier(0.25,0.1,0.25,1)] disabled:pointer-events-none disabled:opacity-50"
  
  const variants = {
    primary: "bg-primary text-on-primary hover:bg-opacity-90 rounded-md",
    secondary: "bg-surface-highest text-on-surface hover:brightness-95 rounded-md",
  }

  const sizes = {
    default: "h-10 px-4 py-2",
    sm: "h-9 rounded-md px-3",
    lg: "h-11 rounded-md px-8",
    icon: "h-10 w-10 rounded-full",
  }

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      ref={ref}
      {...props}
    />
  )
})
Button.displayName = "Button"

export { Button }
