import React, { useState } from 'react'
import { Card } from './ui/Card'
import { Input } from './ui/Input'
import { Button } from './ui/Button'
import { Plus, Loader2 } from 'lucide-react'
import { cn } from '../lib/utils'
import { collection, addDoc } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { TIERS, TIER_BG, STARTING_MU } from '../lib/constants'
import { useToast } from './ui/ToastProvider'

export function Register() {
  const { showToast } = useToast()
  const [name, setName] = useState('')
  const [selectedTier, setSelectedTier] = useState('Beginner')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      showToast('Please enter a player name', 'warning')
      return
    }

    setSubmitting(true)
    try {
      await addDoc(collection(db, 'players'), {
        name: trimmed,
        colour_tier: selectedTier,
        mu: STARTING_MU[selectedTier],
        sigma: 8.333,
        games_played: 0,
      })
      showToast(`${trimmed} added to roster`, 'success')
      setName('')
      setSelectedTier('Beginner')
    } catch (err) {
      console.error('Failed to register player:', err)
      showToast('Failed to add player', 'warning')
    }
    setSubmitting(false)
  }

  return (
    <Card className="p-8 flex flex-col gap-6">
      <h2 className="text-2xl font-bold">Register Player</h2>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold tracking-wider text-on-surface-variant uppercase">Full Name</label>
        <Input
          placeholder="Enter the name..."
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold tracking-wider text-on-surface-variant uppercase">Skill Tier</label>
        <div className="grid grid-cols-2 gap-3">
          {TIERS.map((tier) => (
            <button
              key={tier}
              onClick={() => setSelectedTier(tier)}
              className={cn(
                'flex items-center justify-center gap-2 h-10 rounded-sm text-[11px] font-bold tracking-wider transition-colors',
                selectedTier === tier
                  ? 'bg-surface-highest text-on-surface shadow-sm'
                  : 'bg-surface-low text-on-surface-variant hover:bg-surface-highest/50'
              )}
            >
              <span className={cn('w-1.5 h-1.5 rounded-full', TIER_BG[tier])} />
              {tier.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <Button
        onClick={handleSubmit}
        disabled={submitting}
        className="mt-2 h-12 text-[13px] font-bold tracking-widest uppercase flex items-center gap-2"
      >
        {submitting ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} strokeWidth={3} />}
        {submitting ? 'Adding...' : 'Add Player'}
      </Button>
    </Card>
  )
}
