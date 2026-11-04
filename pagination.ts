export function pageCount(total: number, limit: number): number {
  return Math.max(1, Math.ceil(total / Math.max(1, limit)));
}

/** Compact page list with ellipses, e.g. [1, '…', 4, 5, 6, '…', 20]. */
export function pageWindow(current: number, last: number, radius = 1): (number | '…')[] {
  const pages = new Set<number>([1, last]);
  for (let p = current - radius; p <= current + radius; p++) if (p >= 1 && p <= last) pages.add(p);
  const sorted = [...pages].sort((a, b) => a - b);
  const out: (number | '…')[] = [];
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push('…');
    out.push(p);
  });
  return out;
}
