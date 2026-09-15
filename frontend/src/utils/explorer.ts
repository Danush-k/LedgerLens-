const EXPLORER_BASE: Record<string, string> = {
  ethereum: 'https://etherscan.io/address/',
  bsc: 'https://bscscan.com/address/',
  polygon: 'https://polygonscan.com/address/',
  bitcoin: 'https://blockstream.info/address/',
}

const EXPLORER_TX_BASE: Record<string, string> = {
  ethereum: 'https://etherscan.io/tx/',
  bsc: 'https://bscscan.com/tx/',
  polygon: 'https://polygonscan.com/tx/',
  bitcoin: 'https://blockstream.info/tx/',
  tron: 'https://tronscan.org/#/transaction/',
}

export function explorerUrl(chain: string, address: string): string | null {
  const base = EXPLORER_BASE[chain]
  return base ? `${base}${address}` : null
}

export function explorerTxUrl(chain: string, txHash: string): string | null {
  const base = EXPLORER_TX_BASE[chain] || EXPLORER_TX_BASE.bitcoin
  return base ? `${base}${txHash}` : null
}
