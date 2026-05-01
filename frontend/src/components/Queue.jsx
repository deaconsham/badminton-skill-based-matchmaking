import React, { useState, useEffect } from 'react'
import { Card } from './ui/Card'
import { ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '../lib/utils'
import { TIER_BG, TIER_COLOUR } from '../lib/constants'

function formatWait(checkInTime) {
  const seconds = Math.floor(Date.now() / 1000 - checkInTime)
  if (seconds < 60) return 'Just queued'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

function TierDot({ tier }) {
  return <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', TIER_BG[tier] || TIER_BG.Beginner)} />
}

export function Queue({ standby, queue, allPlayers, itemsPerPage = 6 }) {
  const [currentPage, setCurrentPage] = useState(0)
  const [, setTick] = useState(0)
  const totalPages = Math.max(1, Math.ceil(queue.length / itemsPerPage))

  const activePage = Math.max(0, Math.min(currentPage, totalPages - 1))

  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 60000)
    return () => clearInterval(interval)
  }, [])

  const paginatedQueue = queue.slice(activePage * itemsPerPage, (activePage + 1) * itemsPerPage)
  const nextPage = () => setCurrentPage((p) => Math.min(totalPages - 1, Math.max(0, Math.min(p, totalPages - 1)) + 1))
  const prevPage = () => setCurrentPage((p) => Math.max(0, Math.min(p, totalPages - 1) - 1))

  const resolvePlayerData = (ids, names) => {
    if (!ids || !allPlayers) return (names || []).map((n) => ({ name: n, tier: 'Beginner', rating: 0 }))
    return ids.map((id, i) => {
      const p = allPlayers.find((pl) => pl.id === id)
      return {
        name: p?.name || names?.[i] || id.slice(0, 8),
        tier: p?.tier || 'Beginner',
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
                  <div key={i} className="grid grid-cols-[40px_1fr_8px] items-center gap-2 overflow-hidden">
                    <span className="text-[9px] font-mono text-on-surface-variant w-10 text-left whitespace-nowrap">{p.rating}</span>
                    <span className="text-[12px] font-bold truncate text-right">{p.name}</span>
                    <TierDot tier={p.tier} />
                  </div>
                ))}
              </div>

              <div className="text-[10px] font-bold text-on-surface-variant">VS</div>

              <div className="flex flex-col gap-2">
                <div className="text-[8px] font-bold tracking-widest text-on-surface-variant uppercase text-center mb-0.5">Team B</div>
                {standbyTeamB.map((p, i) => (
                  <div key={i} className="grid grid-cols-[8px_1fr_40px] items-center gap-2 overflow-hidden">
                    <TierDot tier={p.tier} />
                    <span className="text-[12px] font-bold truncate text-left">{p.name}</span>
                    <span className="text-[9px] font-mono text-on-surface-variant w-10 text-right whitespace-nowrap">{p.rating}</span>
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
          <h2 className="text-[13px] font-bold tracking-widest uppercase text-on-surface-variant">Queue</h2>
          <span className="text-[11px] font-medium text-on-surface-variant">{queue.length} Players Waiting</span>
        </div>

        <div className="flex-1 relative overflow-hidden flex flex-col h-[160px]">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div
              key={activePage}
              initial={{ x: 150, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -150, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="grid grid-cols-2 gap-x-10 gap-y-3 w-full"
            >
              {paginatedQueue.map((p, i) => {
                const absoluteIndex = i + activePage * itemsPerPage
                return (
                  <motion.div layout key={p.queueDocId || p.playerId} className="flex items-start gap-3 py-0.5">
                    <span className="text-[11px] font-mono text-on-surface-variant mt-0.5 w-7 shrink-0">
                      #{absoluteIndex + 1}
                    </span>
                    <div className="flex flex-col flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[13px] font-bold truncate">{p.name}</span>
                        {p.requestedTeammate && (
                          <div className="flex items-center text-skill-advanced gap-1">
                             <Link size={10} />
                             <span className="text-[9px] font-medium truncate">
                               {allPlayers?.find(pl => pl.id === p.requestedTeammate)?.name}
                             </span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <TierDot tier={p.tier} />
                        <span className="text-[9px] font-mono tracking-wider text-on-surface-variant uppercase">
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
          'flex items-center justify-between pt-4 mt-auto border-t border-outline-variant',
          totalPages <= 1 && 'invisible'
        )}>
          <span className="text-[11px] font-medium text-on-surface-variant">
            {activePage + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={prevPage}
              disabled={activePage === 0}
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
