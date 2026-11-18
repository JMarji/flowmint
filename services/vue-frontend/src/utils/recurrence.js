// Project a Plaid recurring stream's charge dates into a date range (for calendars / "upcoming" lists).
// Dates are local-time ISO strings (YYYY-MM-DD). Irregular streams only show their predicted next date.

export function toIsoDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const parse = (iso) => (iso ? new Date(`${iso}T00:00:00`) : null)
const daysIn = (y, m) => new Date(y, m + 1, 0).getDate()
const clampDay = (y, m, day) => new Date(y, m, Math.min(day, daysIn(y, m)))

/**
 * @param {object} stream  { frequency, next_date, last_date, first_date }
 * @param {string} startIso inclusive
 * @param {string} endIso   inclusive
 * @returns {string[]} ISO dates
 */
export function projectDates(stream, startIso, endIso) {
  const anchor = parse(stream.next_date) || parse(stream.last_date)
  if (!anchor) return []
  const start = parse(startIso)
  const end = parse(endIso)
  // Never project before the stream existed.
  const floor = parse(stream.first_date)
  const lo = floor && floor > start ? floor : start
  const out = []
  const push = (d) => { if (d >= lo && d <= end) out.push(toIsoDate(d)) }

  switch (stream.frequency) {
    case 'WEEKLY':
    case 'BIWEEKLY': {
      const step = stream.frequency === 'WEEKLY' ? 7 : 14
      const d = new Date(anchor)
      while (d > lo) d.setDate(d.getDate() - step)
      while (d <= end) { push(new Date(d)); d.setDate(d.getDate() + step) }
      break
    }
    case 'MONTHLY':
    case 'SEMI_MONTHLY': {
      const days = stream.frequency === 'MONTHLY'
        ? [anchor.getDate()]
        : [anchor.getDate(), ((anchor.getDate() + 14) % 30) + 1] // roughly twice a month, ~15 days apart
      for (let y = start.getFullYear(), m = start.getMonth(); new Date(y, m, 1) <= end; m === 11 ? (y++, m = 0) : m++) {
        for (const day of days) push(clampDay(y, m, day))
      }
      break
    }
    case 'ANNUALLY': {
      for (let y = start.getFullYear(); y <= end.getFullYear(); y++) push(clampDay(y, anchor.getMonth(), anchor.getDate()))
      break
    }
    default: {
      const next = parse(stream.next_date)
      if (next) push(next)
    }
  }
  return [...new Set(out)].sort()
}
