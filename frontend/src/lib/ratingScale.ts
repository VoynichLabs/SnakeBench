const DEFAULT_TARGET_MIN = 1000;
const DEFAULT_TARGET_MAX = 1800;
const MIN_EFFECTIVE_RANGE = 5; // Avoid huge jumps when the spread is tiny
const LOGISTIC_SPAN = 6; // Wider span keeps the middle dispersed before leveling off

export type EloLikeScaler = {
  scale: (rating?: number | null) => number;
  meta: {
    min: number;
    max: number;
    mid: number;
    targetMin: number;
    targetMax: number;
    sampleSize: number;
  };
};

/**
 * Builds a monotonic scaler that maps TrueSkill values to an ELO-like band
 * purely for display. Ranking order stays unchanged.
 */
export function createEloLikeScaler(
  ratings: Array<number | null | undefined>,
  options?: { targetMin?: number; targetMax?: number }
): EloLikeScaler {
  const targetMin = options?.targetMin ?? DEFAULT_TARGET_MIN;
  const targetMax = options?.targetMax ?? DEFAULT_TARGET_MAX;
  const targetMid = (targetMin + targetMax) / 2;

  const cleanRatings = ratings.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value)
  );

  if (cleanRatings.length === 0) {
    return {
      scale: () => Math.round(targetMid),
      meta: {
        min: targetMid,
        max: targetMid,
        mid: targetMid,
        targetMin,
        targetMax,
        sampleSize: 0
      }
    };
  }

  const min = Math.min(...cleanRatings);
  const max = Math.max(...cleanRatings);
  const range = Math.max(max - min, MIN_EFFECTIVE_RANGE);
  const mid = (min + max) / 2;
  const logisticScale = range / LOGISTIC_SPAN; // Wider middle, soft leveling at top

  const scale = (rating?: number | null) => {
    if (typeof rating !== "number" || !Number.isFinite(rating)) {
      return Math.round(targetMid);
    }

    const normalized =
      1 / (1 + Math.exp(-1 * (rating - mid) / logisticScale));
    const scaled = targetMin + normalized * (targetMax - targetMin);
    return Math.round(scaled);
  };

  return {
    scale,
    meta: {
      min,
      max,
      mid,
      targetMin,
      targetMax,
      sampleSize: cleanRatings.length
    }
  };
}
