import { Building2, ExternalLink, Mail, X } from 'lucide-react'

interface Props {
  open: boolean
  onClose: () => void
}

const VASP_DIRECTORY = [
  {
    name: 'Binance',
    jurisdiction: 'Global (Cayman / Global)',
    email: 'lawenforcement@binance.com',
    portal: 'https://www.binance.com/en/support/law-enforcement',
    notes: 'Requires official law enforcement domain (.gov.in / .police.gov.in) for Sec 91/94 preservation requests.',
  },
  {
    name: 'CoinDCX',
    jurisdiction: 'India (FIU-IND Registered)',
    email: 'compliance@coindcx.com',
    portal: 'https://coindcx.com/legal/law-enforcement',
    notes: 'Accepts Section 91 CrPC / Section 94 BNSS notices issued by Indian Police Officers.',
  },
  {
    name: 'WazirX',
    jurisdiction: 'India (FIU-IND Registered)',
    email: 'nodal@wazirx.com',
    portal: 'https://wazirx.com/legal/law-enforcement',
    notes: '24/7 dedicated Indian LEA response cell for emergency account freeze orders.',
  },
  {
    name: 'CoinSwitch Kuber',
    jurisdiction: 'India (FIU-IND Registered)',
    email: 'legal@coinswitch.co',
    portal: 'https://coinswitch.co/law-enforcement',
    notes: 'Official FIU nodal response team for wallet preservation and KYC requests.',
  },
  {
    name: 'OKX',
    jurisdiction: 'Global (Seychelles / Global)',
    email: 'lawenforcement@okx.com',
    portal: 'https://www.okx.com/law-enforcement',
    notes: 'Global compliance desk for multi-hop cashout wallet freezes.',
  },
  {
    name: 'Bybit',
    jurisdiction: 'Global (UAE / Dubai)',
    email: 'lea@bybit.com',
    portal: 'https://www.bybit.com/en-US/help-center/law-enforcement',
    notes: 'Requires crime ref number and officer rank in subject line.',
  },
]

export function VaspDirectoryModal({ open, onClose }: Props) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 backdrop-blur-xs p-4">
      <div className="w-full max-w-2xl rounded-xl border border-ink-100 bg-surface shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-ink-100 px-6 py-4">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-brand-600" />
            <div>
              <h2 className="text-base font-bold text-ink-900">VASP Law Enforcement Response Directory</h2>
              <p className="text-xs text-ink-500">Official nodal officer emails &amp; LEA portals for Sec 91/94 freeze directives.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700 cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Directory List */}
        <div className="p-6 overflow-y-auto space-y-3">
          {VASP_DIRECTORY.map((v, idx) => (
            <div key={idx} className="rounded-lg border border-ink-200 bg-surface p-4 shadow-2xs space-y-2">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-bold text-ink-900">{v.name}</h3>
                  <span className="text-[11px] font-medium text-ink-500">{v.jurisdiction}</span>
                </div>

                <a
                  href={`mailto:${v.email}?subject=Sec%2094%20BNSS%20Preservation%20Notice%20-%20Urgent`}
                  className="inline-flex items-center gap-1.5 rounded-md bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white shadow-2xs hover:bg-brand-700 cursor-pointer"
                >
                  <Mail size={13} />
                  Send Directive ({v.email})
                </a>
              </div>

              <p className="text-xs text-ink-600 bg-ink-50 p-2 rounded border border-ink-100">{v.notes}</p>

              <div className="flex justify-end pt-1">
                <a
                  href={v.portal}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-brand-600 hover:text-brand-700 cursor-pointer"
                >
                  Official LEA Portal <ExternalLink size={12} />
                </a>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t border-ink-100 bg-ink-50 px-6 py-3 text-right">
          <button
            onClick={onClose}
            className="rounded-lg border border-ink-200 bg-surface px-4 py-2 text-xs font-semibold text-ink-700 shadow-2xs hover:bg-ink-100 cursor-pointer"
          >
            Close Directory
          </button>
        </div>
      </div>
    </div>
  )
}
