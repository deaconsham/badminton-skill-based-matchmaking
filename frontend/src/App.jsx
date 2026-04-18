import { useState, useEffect } from 'react'
import { Register } from './components/Register'
import { Courts } from './components/Courts'
import { PlayerList } from './components/PlayerList'
import { Queue } from './components/Queue'
import { PlayerModel } from './components/PlayerModel'
import { ToastProvider, useToast } from './components/ui/ToastProvider'
import { useFirestore } from './hooks/useFirestore'

function Dashboard() {
  const { showToast } = useToast()
  const { players, queue, queueSet, courts, standby, loading, consumeTierChanges } = useFirestore()
  const [selectedPlayer, setSelectedPlayer] = useState(null)

  useEffect(() => {
    const changes = consumeTierChanges()
    for (const c of changes) {
      if (['Green', 'Yellow', 'Orange', 'Red'].indexOf(c.newTier) > ['Green', 'Yellow', 'Orange', 'Red'].indexOf(c.oldTier)) {
        showToast(`🎉 ${c.name} has been promoted to ${c.newTier}!`, 'success')
      } else {
        showToast(`${c.name} is now in the ${c.newTier} tier`, 'info')
      }
    }
  }, [players])

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
        <span className="text-[11px] font-mono text-on-surface-variant">
          {players.length} players · {queue.length} in queue
        </span>
      </header>

      <main className="grid lg:grid-cols-[1fr_2fr] gap-x-8 gap-y-8 items-stretch">
        <div className="flex flex-col gap-8 h-full">
          <Register />
          <PlayerList
            players={players}
            queue={queue}
            queueSet={queueSet}
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
