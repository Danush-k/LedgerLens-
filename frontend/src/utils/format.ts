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
