import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Trash2, AlertTriangle } from 'lucide-react'
import { doc, deleteDoc, updateDoc } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { cn } from '../lib/utils'
import { SIGMA_CONFIDENCE_THRESHOLD } from '../lib/constants'
import { useToast } from './ui/ToastProvider'

const tierColours = {
  Green: 'bg-skill-green',
  Yellow: 'bg-skill-yellow',
  Orange: 'bg-skill-orange',
  Red: 'bg-skill-red',
}

const tierLabels = {
  Green: 'Beginner',
  Yellow: 'Intermediate',
  Orange: 'Advanced',
  Red: 'Skilled',
}

export function PlayerModel({ player, allPlayers, queue, queueSet, onClose }) {
  const { showToast } = useToast()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [saving, setSaving] = useState(false)

  if (!player) return null

  const isCheckedIn = queueSet.has(player.id)
  const queueEntry = queue.find((q) => q.playerId === player.id)
  const rank = allPlayers.findIndex((p) => p.id === player.id) + 1
  const isCalibrating = player.sigma > SIGMA_CONFIDENCE_THRESHOLD
  const confidencePercent = Math.max(0, Math.min(100, Math.round((1 - player.sigma / 8.333) * 100)))

  const checkedInPlayers = queue
    .filter((q) => q.playerId !== player.id)
    .map((q) => {
      const p = allPlayers.find((pl) => pl.id === q.playerId)
      return p ? { id: p.id, name: p.name, queueDocId: q.queueDocId } : null
    })
    .filter(Boolean)

  const handleRequestChange = async (field, value) => {
    if (!queueEntry) return
    setSaving(true)
    try {
      await updateDoc(doc(db, 'queue', queueEntry.queueDocId), {
        [field]: value || null,
      })
      showToast('Match request updated', 'success')
    } catch (err) {
      console.error('Failed to update request:', err)
      showToast('Failed to update request', 'warning')
    }
    setSaving(false)
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      if (queueEntry) {
        await deleteDoc(doc(db, 'queue', queueEntry.queueDocId))
      }
      await deleteDoc(doc(db, 'players', player.id))
      showToast(`${player.name} removed from roster`, 'info')
      onClose()
    } catch (err) {
      console.error('Failed to delete player:', err)
      showToast('Failed to delete player', 'warning')
      setDeleting(false)
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-40 bg-on-surface/20 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          className="bg-surface-lowest rounded-lg shadow-xl w-full max-w-md overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-6 pb-0 flex items-start justify-between">
            <div className="flex items-center gap-3">
              <span className={cn('w-3 h-3 rounded-full', tierColours[player.tier])} />
              <div>
                <h2 className="text-xl font-bold">{player.name}</h2>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold tracking-widest uppercase text-on-surface-variant">
                    {tierLabels[player.tier]} · {rank} of {allPlayers.length}
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md hover:bg-on-surface/10 transition-colors text-on-surface-variant"
            >
              <X size={18} />
            </button>
          </div>

          <div className="p-6 flex flex-col gap-5">
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Rating" value={player.rating} />
              <StatBox label="μ (Mu)" value={player.mu.toFixed(2)} />
              <StatBox label="σ (Sigma)" value={player.sigma.toFixed(2)} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <StatBox label="Games Played" value={player.gamesPlayed} />
              <div className="bg-surface-low rounded-md p-3 flex flex-col gap-1.5">
                <span className="text-[9px] font-bold tracking-widest uppercase text-on-surface-variant">
                  Confidence
                </span>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-surface-highest rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all duration-700',
                        isCalibrating ? 'bg-skill-orange' : 'bg-skill-green'
                      )}
                      style={{ width: `${confidencePercent}%` }}
                    />
                  </div>
                  <span className="text-[11px] font-mono font-bold">
                    {confidencePercent}%
                  </span>
                </div>
              </div>
            </div>

            {isCheckedIn && (
              <div className="flex flex-col gap-3">
                <span className="text-[10px] font-bold tracking-widest uppercase text-on-surface-variant">
                  Match Requests
                </span>
                <div className="grid grid-cols-3 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[8px] font-bold tracking-widest text-secondary uppercase opacity-70">
                      Partner
                    </label>
                    <select
                      disabled={saving}
                      value={queueEntry?.requestedTeammate || ''}
                      onChange={(e) => handleRequestChange('requested_teammate', e.target.value)}
                      className="h-9 rounded-sm bg-surface-low px-2 text-[11px] font-medium text-on-surface focus:outline-none focus:ring-1 focus:ring-secondary/30 transition-all cursor-pointer truncate"
                    >
                      <option value="">None</option>
                      {checkedInPlayers
                        .filter(p => p.id !== (queueEntry?.requestedOpponent1) && p.id !== (queueEntry?.requestedOpponent2))
                        .map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[8px] font-bold tracking-widest text-skill-orange uppercase opacity-70">
                      Opponent 1
                    </label>
                    <select
                      disabled={saving}
                      value={queueEntry?.requestedOpponent1 || ''}
                      onChange={(e) => handleRequestChange('requested_opponent1', e.target.value)}
                      className="h-9 rounded-sm bg-surface-low px-2 text-[11px] font-medium text-on-surface focus:outline-none focus:ring-1 focus:ring-skill-orange/30 transition-all cursor-pointer truncate"
                    >
                      <option value="">None</option>
                      {checkedInPlayers
                        .filter(p => p.id !== (queueEntry?.requestedTeammate) && p.id !== (queueEntry?.requestedOpponent2))
                        .map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[8px] font-bold tracking-widest text-skill-orange uppercase opacity-70">
                      Opponent 2
                    </label>
                    <select
                      disabled={saving}
                      value={queueEntry?.requestedOpponent2 || ''}
                      onChange={(e) => handleRequestChange('requested_opponent2', e.target.value)}
                      className="h-9 rounded-sm bg-surface-low px-2 text-[11px] font-medium text-on-surface focus:outline-none focus:ring-1 focus:ring-skill-orange/30 transition-all cursor-pointer truncate"
                    >
                      <option value="">None</option>
                      {checkedInPlayers
                        .filter(p => p.id !== (queueEntry?.requestedTeammate) && p.id !== (queueEntry?.requestedOpponent1))
                        .map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                    </select>
                  </div>
                </div>
              </div>
            )}

            <div className="border-t border-outline-variant pt-4">
              {!confirmDelete ? (
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="flex items-center gap-2 text-[11px] font-bold tracking-wider uppercase text-skill-red hover:bg-skill-red/10 px-3 py-2 rounded-sm transition-colors"
                >
                  <Trash2 size={14} />
                  Delete Player
                </button>
              ) : (
                <div className="flex items-center gap-3">
                  <AlertTriangle size={16} className="text-skill-red flex-shrink-0" />
                  <span className="text-[12px] font-medium text-on-surface-variant flex-1">
                    Remove {player.name} permanently?
                  </span>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="h-8 px-4 rounded-sm text-[10px] font-bold tracking-wider uppercase bg-skill-red text-on-primary hover:bg-skill-red/90 transition-colors disabled:opacity-50"
                  >
                    {deleting ? 'Removing...' : 'Confirm'}
                  </button>
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="h-8 px-3 rounded-sm text-[10px] font-bold tracking-wider uppercase bg-surface-low text-on-surface hover:bg-surface-highest transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

function StatBox({ label, value }) {
  return (
    <div className="bg-surface-low rounded-md p-3 flex flex-col gap-1">
      <span className="text-[9px] font-bold tracking-widest uppercase text-on-surface-variant">
        {label}
      </span>
      <span className="text-lg font-bold font-mono">{value}</span>
    </div>
  )
}
