export function toFiniteNumber(value) {
  const parsed = Number.parseFloat(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}
