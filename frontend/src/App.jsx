import { useState, useEffect } from 'react'
import { Register } from './components/Register'
import { Courts } from './components/Courts'
import { PlayerList } from './components/PlayerList'
import { Queue } from './components/Queue'
import { PlayerModel } from './components/PlayerModel'
import { ToastProvider, useToast } from './components/ui/ToastProvider'
import { useFirestore } from './hooks/useFirestore'
import { doc, setDoc, getDoc, writeBatch } from 'firebase/firestore'
import { db } from './lib/firebase'

function ToggleSwitch({ checked, onChange, label, disabled }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={`
        relative inline-flex items-center h-6 w-11 rounded-full transition-colors duration-200 focus:outline-none
        ${checked ? 'bg-skill-advanced' : 'bg-on-surface/20'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
      title={label}
    >
      <span
        className={`
          inline-block w-4 h-4 bg-white rounded-full shadow transition-transform duration-200
          ${checked ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
    </button>
  )
}

function Dashboard() {
  const { showToast } = useToast()
  const { players, queue, queueSet, inMatchSet, courts, standby, loading } = useFirestore()
  const [selectedPlayer, setSelectedPlayer] = useState(null)
  const [engineEnabled, setEngineEnabled] = useState(false)
  const [engineLoading, setEngineLoading] = useState(true)
  const [confirmCheckOutAll, setConfirmCheckOutAll] = useState(false)
  const [checkingOutAll, setCheckingOutAll] = useState(false)

  useEffect(() => {
    getDoc(doc(db, 'settings', 'engine'))
      .then((snap) => {
        if (snap.exists()) setEngineEnabled(snap.data().enabled ?? false)
      })
      .catch(console.error)
      .finally(() => setEngineLoading(false))
  }, [])

  const handleEngineToggle = async (val) => {
    setEngineLoading(true)
    try {
      await setDoc(doc(db, 'settings', 'engine'), { enabled: val }, { merge: true })
      setEngineEnabled(val)
      showToast(val ? 'Matchmaking enabled' : 'Matchmaking paused', val ? 'success' : 'info')
    } catch (err) {
      console.error(err)
      showToast('Failed to update matchmaking state', 'warning')
    }
    setEngineLoading(false)
  }

  const handleCheckOutAll = async () => {
    const standbyPlayerCount = standby ? 4 : 0
    const totalCount = queue.length + standbyPlayerCount
    if (totalCount === 0) {
      showToast('No players to check out', 'info')
      return
    }
    setCheckingOutAll(true)
    try {
      const batch = writeBatch(db)
      for (const entry of queue) {
        batch.delete(doc(db, 'queue', entry.queueDocId))
        batch.update(doc(db, 'players', entry.playerId), { is_in_queue: false })
      }
      if (standby) {
        batch.update(doc(db, 'matches', standby.id), { status: 'voided' })
        const standbyPlayers = [...(standby.teamA || []), ...(standby.teamB || [])]
        for (const pid of standbyPlayers) {
          batch.update(doc(db, 'players', pid), { is_in_standby: false })
        }
      }
      await batch.commit()
      showToast(`Checked out ${totalCount} player${totalCount !== 1 ? 's' : ''}`, 'info')
    } catch (err) {
      console.error(err)
      showToast('Failed to check out all players', 'warning')
    }
    setCheckingOutAll(false)
    setConfirmCheckOutAll(false)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium text-on-surface-variant">Connecting to database...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-6 md:p-8 max-w-[1600px] mx-auto flex flex-col gap-6">
      <header className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight">Fuel Badminton Academy</h1>
        <div className="flex items-center gap-4">
          <span className="text-[11px] font-mono text-on-surface-variant">
            {players.length} players · {queue.length} in queue
          </span>

          {!confirmCheckOutAll ? (
            <button
              onClick={() => setConfirmCheckOutAll(true)}
              disabled={queue.length === 0}
              className="h-8 px-3 rounded-md text-[10px] font-bold tracking-wider uppercase bg-skill-beginner text-white hover:bg-skill-beginner/90 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              CHECK-OUT ALL
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-skill-beginner uppercase animate-pulse">Are you sure?</span>
              <button
                onClick={handleCheckOutAll}
                disabled={checkingOutAll}
                className="h-8 px-3 rounded-md text-[10px] font-bold tracking-wider uppercase bg-skill-beginner text-white hover:bg-skill-beginner/90 active:scale-95 transition-all disabled:opacity-50"
              >
                {checkingOutAll ? 'Clearing...' : 'CONFIRM'}
              </button>
              <button
                onClick={() => setConfirmCheckOutAll(false)}
                className="h-8 px-3 rounded-md text-[10px] font-bold tracking-wider uppercase bg-surface-low text-on-surface hover:bg-surface-highest active:scale-95 transition-all"
              >
                CANCEL
              </button>
            </div>
          )}

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold tracking-widest uppercase text-on-surface-variant">
              Matchmaking
            </span>
            <ToggleSwitch
              checked={engineEnabled}
              onChange={handleEngineToggle}
              label={engineEnabled ? 'Disable matchmaking' : 'Enable matchmaking'}
              disabled={engineLoading}
            />
          </div>
        </div>
      </header>

      <main className="grid lg:grid-cols-[1fr_2fr] gap-x-8 gap-y-8 items-stretch">
        <div className="flex flex-col gap-8 h-full">
          <Register />
          <PlayerList
            players={players}
            queue={queue}
            queueSet={queueSet}
            inMatchSet={inMatchSet}
            onPlayerClick={setSelectedPlayer}
          />
        </div>

        <div className="flex flex-col gap-8 h-full">
          <Courts courts={courts} allPlayers={players} />
          <div className="grid lg:grid-cols-2 gap-8 h-full">
            <Queue
              standby={standby}
              queue={queue}
              allPlayers={players}
              itemsPerPage={4}
            />
          </div>
        </div>
      </main>

      {selectedPlayer && (
        <PlayerModel
          player={selectedPlayer}
          allPlayers={players}
          queue={queue}
          queueSet={queueSet}
          onClose={() => setSelectedPlayer(null)}
        />
      )}
    </div>
  )
}

function App() {
  return (
    <ToastProvider>
      <Dashboard />
    </ToastProvider>
  )
}

export default App
