import * as React from "react"
import { cn } from "../../lib/utils"

export function MatchMeter({ scoreA, scoreB, className }) {
  const total = scoreA + scoreB
  const percentA = total > 0 ? (scoreA / total) * 100 : 50

  return (
    <div className={cn("relative h-2 w-full bg-surface-low rounded-full overflow-hidden flex", className)}>
      <div 
        className="h-full bg-primary-container transition-all duration-700 ease-[cubic-bezier(0.25,0.1,0.25,1)]" 
        style={{ width: `${percentA}%` }} 
      />
      <div 
        className="h-full bg-primary transition-all duration-700 ease-[cubic-bezier(0.25,0.1,0.25,1)]" 
        style={{ width: `${100 - percentA}%` }} 
      />
    </div>
  )
}
