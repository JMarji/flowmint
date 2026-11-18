// Shared look for mortgage payment status (Properties list + Property detail).
const STYLES = {
  paid: { icon: 'pi-check-circle', color: 'var(--mint)', bg: 'rgba(61,219,184,0.14)' },
  due: { icon: 'pi-clock', color: '#fbbf24', bg: 'rgba(251,191,36,0.14)' },
  behind: { icon: 'pi-exclamation-triangle', color: '#f87171', bg: 'rgba(248,113,113,0.14)' },
  unknown: { icon: 'pi-question-circle', color: 'var(--text-muted)', bg: 'var(--surface-2)' },
  none: { icon: 'pi-minus-circle', color: 'var(--text-muted)', bg: 'var(--surface-2)' },
}

export const mortgageStatusStyle = (status) => STYLES[status] || STYLES.unknown

export const mortgageSourceLabel = (source) =>
  ({ plaid: 'From your servicer via Plaid', payments: 'From recorded payments' }[source] || '')
