const EXPLORER_BASE: Record<string, string> = {
  ethereum: 'https://etherscan.io/address/',
  bsc: 'https://bscscan.com/address/',
  polygon: 'https://polygonscan.com/address/',
  bitcoin: 'https://blockstream.info/address/',
}

export function explorerUrl(chain: string, address: string): string | null {
  const base = EXPLORER_BASE[chain]
  return base ? `${base}${address}` : null
}
