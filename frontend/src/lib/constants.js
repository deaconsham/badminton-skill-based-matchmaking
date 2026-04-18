export const RATING_RANGES = {
  Green: [0, 999],
  Yellow: [1000, 1499],
  Orange: [1500, 1999],
  Red: [2000, 9999],
}

export const STARTING_MU = {
  Green: 15.0,
  Yellow: 25.0,
  Orange: 35.0,
  Red: 45.0,
}

export const SIGMA_CONFIDENCE_THRESHOLD = 6.0

export const computeRating = (mu) => Math.max(0, Math.min(9999, Math.round(mu * 50)))
