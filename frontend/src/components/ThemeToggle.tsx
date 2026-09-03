import { Laptop, Moon, Sun } from 'lucide-react'
import { useTheme } from '../theme/ThemeContext'

const OPTIONS = [
  { value: 'light' as const, icon: Sun, label: 'Light theme' },
  { value: 'system' as const, icon: Laptop, label: 'Match system theme' },
  { value: 'dark' as const, icon: Moon, label: 'Dark theme' },
]

export function ThemeToggle() {
  const { choice, setChoice } = useTheme()

  return (
    <div className="flex items-center gap-0.5 rounded-lg bg-chrome-surface p-0.5">
      {OPTIONS.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          onClick={() => setChoice(value)}
          title={label}
          aria-label={label}
          aria-pressed={choice === value}
          className={`cursor-pointer flex h-6 w-6 items-center justify-center rounded-md transition-colors ${
            choice === value
              ? 'bg-brand-500/20 text-brand-300'
              : 'text-chrome-text-secondary hover:text-chrome-text-primary'
          }`}
        >
          <Icon size={13} />
        </button>
      ))}
    </div>
  )
}
