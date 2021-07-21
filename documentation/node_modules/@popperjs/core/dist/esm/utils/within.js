export default function within(min, value, max) {
  return Math.max(min, Math.min(value, max));
}