/** Formats a chain-native amount for display. Small transfers (a fraction
 * of a cent in BTC/ETH terms) round to "0.0000" at a fixed 4 decimals,
 * which reads as "nothing moved" when real funds did — so this scales
 * precision to the value instead of using one fixed decimal count. */
export function formatAmount(value: number): string {
  if (value === 0) return '0'
  if (value < 0.0001) {
    return value.toFixed(8).replace(/0+$/, '').replace(/\.$/, '')
  }
  return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}


const CHAIN_UNITS: Record<string, string> = {
  bitcoin: 'BTC', ethereum: 'ETH', bsc: 'BNB', polygon: 'MATIC', tron: 'USDT',
}

/**
 * An amount with its unit, written the way an investigator would say it.
 *
 * Dust in whole bitcoin - "0.00008175 BTC" - forces the reader to count
 * decimal places to judge whether it matters, and the evidence text beside
 * it already says "8,175 sats". Two spellings of one number in one row is a
 * reason to doubt both, so this mirrors the backend's convention exactly.
 */
export function formatChainAmount(value: number, chain?: string): string {
  const unit = chain ? CHAIN_UNITS[chain] : undefined
  if (chain === 'bitcoin' && value < 0.001) {  // zero included, so one row never mixes units
    return `${Math.round(value * 100_000_000).toLocaleString()} sats`
  }
  return unit ? `${formatAmount(value)} ${unit}` : formatAmount(value)
}
