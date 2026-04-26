import React, { useState } from 'react'
import { Card } from './ui/Card'
import { Input } from './ui/Input'
import { Search, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '../lib/utils'
import { collection, addDoc, deleteDoc, doc } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { TIER_BG } from '../lib/constants'
import { useToast } from './ui/ToastProvider'

export function PlayerList({ players, queue, queueSet, onPlayerClick }) {
  const { showToast } = useToast()
  const [currentPage, setCurrentPage] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [loadingId, setLoadingId] = useState(null)
  const itemsPerPage = 10

  const filtered = players.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const sorted = [...filtered].sort((a, b) => {
    const aIn = queueSet.has(a.id) ? 1 : 0
    const bIn = queueSet.has(b.id) ? 1 : 0
    if (aIn !== bIn) return bIn - aIn
    return b.rating - a.rating
  })

  const totalPages = Math.max(1, Math.ceil(sorted.length / itemsPerPage))
  const safePage = Math.min(currentPage, totalPages - 1)
  const paginatedPlayers = sorted.slice(safePage * itemsPerPage, (safePage + 1) * itemsPerPage)

  const nextPage = () => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))
  const prevPage = () => setCurrentPage((p) => Math.max(0, p - 1))

  const handleCheckIn = async (player) => {
    setLoadingId(player.id)
    try {
      await addDoc(collection(db, 'queue'), {
        player_id: player.id,
        name: player.name,
        check_in_time: Date.now() / 1000,
        requested_teammate: null,
        requested_opponent1: null,
        requested_opponent2: null,
        unranked_flag: false,
      })
      showToast(`${player.name} checked in`, 'success')
    } catch (err) {
      console.error('Check-in failed:', err)
      showToast('Check-in failed', 'warning')
    }
    setLoadingId(null)
  }

  const handleCheckOut = async (player) => {
    const entry = queue.find((q) => q.playerId === player.id)
    if (!entry) return
    setLoadingId(player.id)
    try {
      await deleteDoc(doc(db, 'queue', entry.queueDocId))
      showToast(`${player.name} checked out`, 'info')
    } catch (err) {
      console.error('Check-out failed:', err)
      showToast('Check-out failed', 'warning')
    }
    setLoadingId(null)
  }

  return (
    <Card className="p-6 flex flex-col gap-5 h-[645px]">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Player List</h2>
        <div className="relative w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={14} />
          <Input
            placeholder="Search players..."
            className="pl-9 h-9 text-xs"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setCurrentPage(0)
            }}
          />
        </div>
      </div>

      <div className="w-full flex flex-col flex-1">
        {/* Table header */}
        <div className="grid grid-cols-[2fr_1.2fr_0.8fr_1fr] border-b border-outline-variant pb-3 mb-1 text-[10px] font-bold tracking-widest text-on-surface-variant uppercase">
          <div>Name</div>
          <div className="text-center">Tier</div>
          <div className="text-center">Rating</div>
          <div className="text-right">Action</div>
        </div>

        <div className="flex flex-col relative overflow-hidden flex-1">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div
              key={safePage}
              initial={{ x: 150, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -150, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="flex flex-col w-full"
            >
              {paginatedPlayers.map((p) => {
                const isCheckedIn = queueSet.has(p.id)
                const isLoading = loadingId === p.id

                return (
                  <div
                    key={p.id}
                    onClick={() => onPlayerClick(p)}
                    className="grid grid-cols-[2fr_1.2fr_0.8fr_1fr] items-center py-2.5 border-b border-outline-variant last:border-0 hover:bg-surface-low/50 transition-colors -mx-4 px-4 overflow-hidden cursor-pointer"
                  >
                    {/* Name column — no dot here */}
                    <div className="pr-2">
                      <span className="text-[13px] font-semibold truncate block">{p.name}</span>
                    </div>

                    {/* Tier column — dot only, centred */}
                    <div className="flex items-center justify-center">
                      <span className={cn('w-2 h-2 rounded-full flex-shrink-0', TIER_BG[p.tier])} />
                    </div>

                    {/* Rating column */}
                    <div className="text-[12px] font-mono text-center tracking-wide text-on-surface-variant whitespace-nowrap">
                      {p.rating}
                    </div>

                    {/* Action column */}
                    <div className="flex justify-end">
                      {isLoading ? (
                        <div className="h-6 flex items-center justify-center px-3">
                          <Loader2 size={12} className="animate-spin text-on-surface-variant" />
                        </div>
                      ) : isCheckedIn ? (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleCheckOut(p) }}
                          className="h-6 px-3 whitespace-nowrap rounded-sm text-[8px] font-bold tracking-wider uppercase bg-skill-beginner text-white hover:bg-skill-beginner/80 active:scale-95 transition-all"
                        >
                          Check-Out
                        </button>
                      ) : (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleCheckIn(p) }}
                          className="h-6 px-3 whitespace-nowrap rounded-sm text-[8px] font-bold tracking-wider uppercase bg-surface-lowest border border-outline-variant text-on-surface hover:bg-surface-low transition-colors"
                        >
                          Check-In
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </motion.div>
          </AnimatePresence>
        </div>

        <div className={cn(
          'flex items-center justify-between pt-3 mt-auto border-t border-outline-variant',
          totalPages <= 1 && 'invisible'
        )}>
          <span className="text-[11px] font-medium text-on-surface-variant">
            Page {safePage + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={prevPage}
              disabled={safePage === 0}
              className="p-1.5 rounded-md hover:bg-on-surface/10 active:bg-on-surface/20 disabled:opacity-30 transition-all text-on-surface-variant"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={nextPage}
              disabled={safePage === totalPages - 1}
              className="p-1.5 rounded-md hover:bg-on-surface/10 active:bg-on-surface/20 disabled:opacity-30 transition-all text-on-surface-variant"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </Card>
  )
}
