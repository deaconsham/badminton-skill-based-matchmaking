export const TIERS = ['Beginner', 'Intermediate', 'Advanced', 'Elite']

export const TIER_BG = {
  Beginner: 'bg-skill-beginner',
  Intermediate: 'bg-skill-intermediate',
  Advanced: 'bg-skill-advanced',
  Elite: 'bg-skill-elite',
}

export const TIER_COLOUR = {
  Beginner: '#ef4444',
  Intermediate: '#3b82f6',
  Advanced: '#06b6d4',
  Elite: '#22c55e',
}

export const RATING_RANGES = {
  Beginner: [0, 999],
  Intermediate: [1000, 1499],
  Advanced: [1500, 1999],
  Elite: [2000, 9999],
}

export const STARTING_MU = {
  Beginner: 15.0,
  Intermediate: 25.0,
  Advanced: 35.0,
  Elite: 45.0,
}

export const computeRating = (mu) => Math.max(0, Math.min(9999, Math.round(mu * 50)))
