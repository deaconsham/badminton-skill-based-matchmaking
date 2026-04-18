import { useState, useEffect, useRef } from 'react'
import { collection, onSnapshot, query, orderBy, where } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { computeRating } from '../lib/constants'

export function useFirestore() {
  const [players, setPlayers] = useState([])
  const [queue, setQueue] = useState([])
  const [matches, setMatches] = useState([])
  const [loading, setLoading] = useState(true)

  const prevPlayersRef = useRef(new Map())

  useEffect(() => {
    const unsubs = []
    let playersLoaded = false
    let queueLoaded = false
    let matchesLoaded = false

    const checkReady = () => {
      if (playersLoaded && queueLoaded && matchesLoaded) setLoading(false)
    }

    const playersQuery = query(collection(db, 'players'))
    unsubs.push(
      onSnapshot(playersQuery, (snap) => {
        const data = snap.docs.map((doc) => {
          const d = doc.data()
          return {
            id: doc.id,
            name: d.name,
            tier: d.colour_tier,
            mu: d.mu,
            sigma: d.sigma,
            gamesPlayed: d.games_played || 0,
            rating: computeRating(d.mu),
          }
        })
        data.sort((a, b) => b.mu - a.mu)
        setPlayers(data)
        playersLoaded = true
        checkReady()
      }, (err) => {
        console.error('Players listener error:', err)
        playersLoaded = true
        checkReady()
      })
    )

    const queueQuery = query(collection(db, 'queue'), orderBy('check_in_time'))
    unsubs.push(
      onSnapshot(queueQuery, (snap) => {
        const data = snap.docs.map((doc) => {
          const d = doc.data()
          return {
            queueDocId: doc.id,
            playerId: d.player_id,
            name: d.name,
            checkInTime: d.check_in_time,
            requestedTeammate: d.requested_teammate || null,
            requestedOpponent: d.requested_opponent || null,
            requestedOpponent1: d.requested_opponent1 || null,
            requestedOpponent2: d.requested_opponent2 || null,
            unrankedFlag: d.unranked_flag || false,
          }
        })
        setQueue(data)
        queueLoaded = true
        checkReady()
      }, (err) => {
        console.error('Queue listener error:', err)
        queueLoaded = true
        checkReady()
      })
    )

    const matchesQuery = query(
      collection(db, 'matches'),
      where('status', 'in', ['in_progress', 'standby'])
    )
    unsubs.push(
      onSnapshot(matchesQuery, (snap) => {
        const data = snap.docs.map((doc) => {
          const d = doc.data()
          return {
            id: doc.id,
            matchNumber: d.match_number,
            courtNumber: d.court_number,
            teamA: d.team_a || [],
            teamB: d.team_b || [],
            teamANames: d.team_a_names || [],
            teamBNames: d.team_b_names || [],
            winner: d.winner,
            unranked: d.unranked || false,
            status: d.status,
            createdAt: d.created_at,
            startedAt: d.started_at || null,
            skillDelta: d.skill_delta ?? null,
          }
        })
        setMatches(data)
        matchesLoaded = true
        checkReady()
      }, (err) => {
        console.error('Matches listener error:', err)
        matchesLoaded = true
        checkReady()
      })
    )

    return () => unsubs.forEach((fn) => fn())
  }, [])

  const tierChanges = useRef([])

  useEffect(() => {
    const prevMap = prevPlayersRef.current
    const changes = []

    for (const player of players) {
      const prev = prevMap.get(player.id)
      if (prev && prev.tier !== player.tier) {
        changes.push({
          name: player.name,
          oldTier: prev.tier,
          newTier: player.tier,
        })
      }
    }

    const newMap = new Map()
    for (const p of players) newMap.set(p.id, p)
    prevPlayersRef.current = newMap

    if (changes.length > 0) {
      tierChanges.current = changes
    }
  }, [players])

  const queueSet = new Set(queue.map((q) => q.playerId))

  const enrichedQueue = queue.map((q) => {
    const player = players.find((p) => p.id === q.playerId)
    return {
      ...q,
      tier: player?.tier || 'Green',
      mu: player?.mu || 0,
      sigma: player?.sigma || 8.333,
      rating: player?.rating || 0,
    }
  })

  const courts = matches
    .filter((m) => m.status === 'in_progress')
    .sort((a, b) => a.courtNumber - b.courtNumber)

  const standby = matches.find((m) => m.status === 'standby') || null

  return {
    players,
    queue: enrichedQueue,
    queueSet,
    matches,
    courts,
    standby,
    loading,
    consumeTierChanges: () => {
      const c = tierChanges.current
      tierChanges.current = []
      return c
    },
  }
}
