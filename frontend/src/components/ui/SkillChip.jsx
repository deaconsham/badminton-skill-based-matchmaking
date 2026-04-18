import * as React from "react"
import { cn } from "../../lib/utils"

const tierColours = {
  Green: { bg: "bg-skill-green/12", text: "text-skill-green/100", dot: "bg-skill-green/100" },
  Yellow: { bg: "bg-skill-yellow/12", text: "text-skill-yellow/100", dot: "bg-skill-yellow/100" },
  Orange: { bg: "bg-skill-orange/12", text: "text-skill-orange/100", dot: "bg-skill-orange/100" },
  Red: { bg: "bg-skill-red/12", text: "text-skill-red/100", dot: "bg-skill-red/100" },
}

export function SkillChip({ tier, label = null }) {
  const colours = tierColours[tier] || tierColours.Green

  return (
    <span className={cn("inline-flex items-center gap-2 px-3 py-1 rounded-xl text-xs font-semibold tracking-wide uppercase", colours.bg, colours.text)}>
      <span className={cn("w-1.5 h-1.5 rounded-full", colours.dot)}></span>
      {label || tier}
    </span>
  )
}
