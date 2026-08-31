const TYPOLOGY_LABELS: Record<string, string> = {
  investment_scam: 'Investment scam',
  task_based_fraud: 'Task-based fraud',
  sextortion: 'Sextortion',
  ransomware: 'Ransomware',
  phishing: 'Phishing',
  darknet: 'Darknet',
  unclassified: 'Unclassified',
}

export function TypologyBadge({ typology }: { typology: string }) {
  const label = TYPOLOGY_LABELS[typology] ?? typology.replace(/_/g, ' ')
  return (
    <span className="inline-flex items-center rounded-md bg-violet-50 px-2 py-0.5 text-xs font-semibold text-violet-700">
      {label}
    </span>
  )
}
