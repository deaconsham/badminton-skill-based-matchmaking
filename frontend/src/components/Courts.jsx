import React, { useState, useEffect } from 'react'
import { Card } from './ui/Card'
import { Trash2 } from 'lucide-react'
import { cn } from '../lib/utils'
import { TIER_BG, TIER_COLOUR, RATING_RANGES, TIERS } from '../lib/constants'
import { doc, updateDoc } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { useToast } from './ui/ToastProvider'

function formatElapsed(startedAt) {
  if (!startedAt) return '0m'
  const seconds = Math.floor(Date.now() / 1000 - startedAt)
  if (seconds < 60) return '<1m'
  return `${Math.floor(seconds / 60)}m`
}

function PlayerRow({ name, rating, tier }) {
  return (
    <div className="flex items-center justify-between py-1">
      <div className="flex items-center gap-2">
        <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', TIER_BG[tier] || TIER_BG.Beginner)} />
        <span className="text-[13px] font-medium truncate max-w-[120px]">{name}</span>
      </div>
      <span className="text-[10px] font-mono tracking-wider text-on-surface-variant uppercase whitespace-nowrap">
        {rating}
      </span>
    </div>
  )
}

function CourtCard({ court, allPlayers }) {
  const { showToast } = useToast()
  const [, setTick] = useState(0)
  const [submitting, setSubmitting] = useState(null)

  const [confirmVoid, setConfirmVoid] = useState(false)

  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 30000)
    return () => clearInterval(interval)
  }, [])

  const resolvePlayer = (id, fallbackName) => {
    if (!allPlayers) return { name: fallbackName || '?', tier: 'Beginner', rating: 0 }
    const p = allPlayers.find((pl) => pl.id === id)
    return p
      ? { name: p.name, tier: p.tier, rating: p.rating }
      : { name: fallbackName || id?.slice(0, 8), tier: 'Beginner', rating: 0 }
  }

  const teamA = court.teamA.map((id, i) => resolvePlayer(id, court.teamANames?.[i]))
  const teamB = court.teamB.map((id, i) => resolvePlayer(id, court.teamBNames?.[i]))

  const handleWin = async (winner) => {
    setSubmitting(winner)
    try {
      await updateDoc(doc(db, 'matches', court.id), { winner, status: 'completed' })
      showToast('Match recorded', 'success')
    } catch (err) {
      console.error('Failed to submit result:', err)
      showToast('Failed to submit match result', 'warning')
    }
    setSubmitting(null)
  }

  const handleVoid = async () => {
    setSubmitting('void')
    try {
      await updateDoc(doc(db, 'matches', court.id), { status: 'voided' })
      showToast('Match voided (players checked out)', 'info')
      setConfirmVoid(false)
    } catch (err) {
      console.error('Failed to void match:', err)
      showToast('Failed to void match', 'warning')
    }
    setSubmitting(null)
  }

  return (
    <div className="relative bg-surface-low rounded-lg p-5 flex flex-col gap-4 h-[340px]">
      <div className="flex items-center justify-between border-b-[0.5px] border-outline-variant pb-3 mb-2">

        <div className="flex items-center gap-2">
          <h3 className="text-xs font-bold tracking-widest text-on-surface-variant uppercase">
            Court {court.courtNumber}
          </h3>
          {court.unranked && (
            <span className="text-[7px] font-bold tracking-widest uppercase px-1.5 py-0.5 rounded-sm bg-skill-orange/15 text-skill-orange">
              Unranked
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="text-[11px] font-bold tracking-wide">
            {formatElapsed(court.startedAt)}{' '}
            <span className="text-on-surface-variant font-medium">ELAPSED</span>
          </div>
          {!confirmVoid ? (
            <button
              onClick={() => setConfirmVoid(true)}
              disabled={submitting !== null}
              className="p-1.5 rounded-md hover:bg-skill-beginner/10 transition-colors text-on-surface-variant hover:text-skill-beginner disabled:opacity-50"
              title="Void Match"
            >
              <Trash2 size={14} />
            </button>
          ) : (
            <div className="flex items-center gap-1.5 bg-surface-lowest px-2 py-1 rounded-md border border-skill-beginner/20 z-10 transition-all absolute right-5 shadow-lg">
              <span className="text-[9px] font-bold text-skill-beginner uppercase tracking-wider pr-1">Are you sure?</span>
              <button
                onClick={handleVoid}
                disabled={submitting !== null}
                className="px-2 py-1 rounded-[4px] text-[8px] font-bold tracking-wider uppercase bg-skill-beginner text-white hover:bg-skill-beginner/90 transition-all disabled:opacity-50"
              >
                Void Match
              </button>
              <button
                onClick={() => setConfirmVoid(false)}
                className="px-2 py-1 rounded-[4px] text-[8px] font-bold tracking-wider uppercase bg-surface-highest text-on-surface hover:bg-surface-highest/80 transition-all"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      <div>
        <h4 className="text-[10px] font-bold tracking-wider text-on-surface-variant uppercase mb-2">Team A</h4>
        {teamA.map((p, i) => <PlayerRow key={i} {...p} />)}
      </div>

      <div className="flex justify-center -my-2">
        <span className="text-[10px] font-bold text-on-surface-variant">VS</span>
      </div>

      <div>
        <h4 className="text-[10px] font-bold tracking-wider text-on-surface-variant uppercase mb-2">Team B</h4>
        {teamB.map((p, i) => <PlayerRow key={i} {...p} />)}
      </div>

      <div className="grid grid-cols-2 gap-3 mt-auto">
        <button
          onClick={() => handleWin('a')}
          disabled={submitting !== null}
          className="bg-surface-lowest hover:bg-surface-highest transition-colors h-9 rounded-sm text-[10px] font-bold tracking-wider uppercase text-on-surface disabled:opacity-50"
        >
          {submitting === 'a' ? 'Submitting...' : 'Team A Won'}
        </button>
        <button
          onClick={() => handleWin('b')}
          disabled={submitting !== null}
          className="bg-surface-lowest hover:bg-surface-highest transition-colors h-9 rounded-sm text-[10px] font-bold tracking-wider uppercase text-on-surface disabled:opacity-50"
        >
          {submitting === 'b' ? 'Submitting...' : 'Team B Won'}
        </button>
      </div>
    </div>
  )
}

export function Courts({ courts, allPlayers }) {
  const courtSlots = [1, 2, 3, 4].map((num) => ({
    courtNumber: num,
    match: courts.find((c) => c.courtNumber === num),
  }))

  return (
    <Card className="p-6 flex flex-col gap-5 h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Active Courts</h2>
        {/* Rating range legend using shared constants */}
        <div className="flex items-center gap-3">
          {TIERS.map((tier) => {
            const [low, high] = RATING_RANGES[tier]
            return (
              <div key={tier} className="flex items-center gap-1.5">
                <span className={cn('w-1.5 h-1.5 rounded-full', TIER_BG[tier])} />
                <span className="text-[9px] font-mono text-on-surface-variant">{low}–{high}</span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-5 h-full">
        {courtSlots.map(({ courtNumber, match }) =>
          match ? (
            <CourtCard key={courtNumber} court={match} allPlayers={allPlayers} />
          ) : (
            <div
              key={courtNumber}
              className="bg-surface-low rounded-lg p-5 flex flex-col h-[340px] border border-dashed border-outline-variant"
            >
              <h3 className="text-xs font-bold tracking-widest text-on-surface-variant uppercase border-b border-outline-variant pb-3 mb-auto">
                Court {courtNumber}
              </h3>
              <div className="flex-1 flex items-center justify-center">
                <span className="text-[11px] text-on-surface-variant/60 font-medium">Waiting for players</span>
              </div>
            </div>
          )
        )}
      </div>
    </Card>
  )
}
