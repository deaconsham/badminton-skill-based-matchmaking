import React, { useState, useEffect } from 'react'
import { Card } from './ui/Card'
import { ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '../lib/utils'

const tierColours = {
  Green: 'bg-skill-green',
  Yellow: 'bg-skill-yellow',
  Orange: 'bg-skill-orange',
  Red: 'bg-skill-red',
}

function formatWait(checkInTime) {
  const seconds = Math.floor(Date.now() / 1000 - checkInTime)
  if (seconds < 60) return 'Just queued'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `Waiting: ${minutes}m`
  const hours = Math.floor(minutes / 60)
  return `Waiting: ${hours}h ${minutes % 60}m`
}

export function Queue({ standby, queue, allPlayers, itemsPerPage = 6 }) {
  const [currentPage, setCurrentPage] = useState(0)
  const [, setTick] = useState(0)
  const totalPages = Math.max(1, Math.ceil(queue.length / itemsPerPage))

  useEffect(() => {
    if (currentPage >= totalPages && totalPages > 0) setCurrentPage(totalPages - 1)
  }, [totalPages, currentPage])

  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 60000)
    return () => clearInterval(interval)
  }, [])

  const paginatedQueue = queue.slice(currentPage * itemsPerPage, (currentPage + 1) * itemsPerPage)

  const nextPage = () => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))
  const prevPage = () => setCurrentPage((p) => Math.max(0, p - 1))

  const resolveNames = (ids, names) => {
    if (names && names.length) return names
    if (!ids || !allPlayers) return []
    return ids.map((id) => {
      const p = allPlayers.find((pl) => pl.id === id)
      return p ? p.name : id.slice(0, 8)
    })
  }

  const resolvePlayerData = (ids, names) => {
    if (!ids || !allPlayers) return (names || []).map((n) => ({ name: n, tier: 'Green', rating: 0 }))
    return ids.map((id, i) => {
      const p = allPlayers.find((pl) => pl.id === id)
      return {
        name: p?.name || names?.[i] || id.slice(0, 8),
        tier: p?.tier || 'Green',
        rating: p?.rating || 0,
      }
    })
  }

  const standbyTeamA = standby ? resolvePlayerData(standby.teamA, standby.teamANames) : []
  const standbyTeamB = standby ? resolvePlayerData(standby.teamB, standby.teamBNames) : []

  return (
    <>
      <Card className="p-5 flex flex-col h-[250px]">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[13px] font-bold tracking-widest uppercase text-on-surface-variant">Match Standby</h2>
          {standby?.unranked && (
            <span className="text-[8px] font-bold tracking-widest uppercase px-2 py-1 rounded-sm bg-skill-orange/15 text-skill-orange">
              Unranked
            </span>
          )}
        </div>

        {standby ? (
          <div className="rounded-lg border border-outline-variant p-3 bg-surface-low mb-auto h-[120px]">
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
              <div className="flex flex-col gap-2">
                <div className="text-[8px] font-bold tracking-widest text-on-surface-variant uppercase text-center mb-0.5">Team A</div>
                {standbyTeamA.map((p, i) => (
                  <div key={i} className="grid grid-cols-[48px_1fr_8px] items-center gap-2 overflow-hidden w-full">
                    <span className="text-[9px] font-mono text-on-surface-variant uppercase flex-shrink-0 w-12 text-left whitespace-nowrap">{p.rating}</span>
                    <span className="text-[12px] font-bold truncate text-right justify-self-end max-w-[80px]">{p.name}</span>
                    <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", tierColours[p.tier])} />
                  </div>
                ))}
              </div>

              <div className="text-[10px] font-bold text-on-surface-variant">VS</div>

              <div className="flex flex-col gap-2">
                <div className="text-[8px] font-bold tracking-widest text-on-surface-variant uppercase text-center mb-0.5">Team B</div>
                {standbyTeamB.map((p, i) => (
                  <div key={i} className="grid grid-cols-[8px_1fr_48px] items-center gap-2 overflow-hidden w-full">
                    <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", tierColours[p.tier])} />
                    <span className="text-[12px] font-bold truncate text-left justify-self-start max-w-[80px]">{p.name}</span>
                    <span className="text-[9px] font-mono text-on-surface-variant uppercase flex-shrink-0 w-12 text-right whitespace-nowrap">{p.rating}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-outline-variant p-3 bg-surface-low mb-auto h-[120px] flex items-center justify-center">
            <span className="text-[10px] text-on-surface-variant font-medium">No match on deck</span>
          </div>
        )}
      </Card>

      <Card className="p-5 flex flex-col h-[250px]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <h2 className="text-[13px] font-bold tracking-widest uppercase text-on-surface-variant">Queue</h2>
          </div>
          <span className="text-[11px] font-medium text-on-surface-variant">{queue.length} Players Waiting</span>
        </div>

        <div className="flex-1 relative overflow-hidden flex flex-col h-[160px]">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div
              key={currentPage}
              initial={{ x: 150, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -150, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="grid grid-cols-2 gap-x-10 gap-y-3 w-full"
            >
              {paginatedQueue.map((p, i) => {
                const absoluteIndex = i + currentPage * itemsPerPage
                return (
                  <motion.div layout key={p.queueDocId || p.playerId} className="flex items-start gap-4 py-0.5">
                    <span className="text-[11px] font-mono text-on-surface-variant mt-0.5 w-7 shrink-0">
                      #{absoluteIndex + 1}
                    </span>
                    <div className="grid grid-cols-[6px_1fr] gap-x-2 items-start flex-1">
                      <span className={cn("w-1.5 h-1.5 rounded-full mt-[5px]", tierColours[p.tier] || tierColours.Green)} />
                      <span className="text-[13px] font-bold truncate max-w-[140px]">{p.name}</span>
                      <span />
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono tracking-wider text-on-surface-variant uppercase">
                          {p.rating}
                        </span>
                        {p.checkInTime && (
                          <span className="text-[9px] font-mono text-on-surface-variant/60 flex items-center gap-1">
                            <Clock size={8} />
                            {formatWait(p.checkInTime)}
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </motion.div>
          </AnimatePresence>
        </div>

        <div className={cn(
          "flex items-center justify-between pt-4 mt-auto border-t border-outline-variant",
          totalPages <= 1 && "invisible"
        )}>
          <span className="text-[11px] font-medium text-on-surface-variant">
            Page {currentPage + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={prevPage}
              disabled={currentPage === 0}
              className="p-1.5 rounded-md hover:bg-on-surface/10 active:bg-on-surface/20 disabled:opacity-30 transition-all text-on-surface-variant"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={nextPage}
              disabled={currentPage === totalPages - 1}
              className="p-1.5 rounded-md hover:bg-on-surface/10 active:bg-on-surface/20 disabled:opacity-30 transition-all text-on-surface-variant"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </Card>
    </>
  )
}
