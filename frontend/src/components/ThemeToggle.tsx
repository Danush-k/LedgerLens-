import { Laptop, Moon, Sun } from 'lucide-react'
import { useTheme } from '../theme/ThemeContext'

const OPTIONS = [
  { value: 'light' as const, icon: Sun, label: 'Light theme' },
  { value: 'system' as const, icon: Laptop, label: 'Match system theme' },
  { value: 'dark' as const, icon: Moon, label: 'Dark theme' },
]

interface Props {
  variant?: 'chrome' | 'surface'
}

export function ThemeToggle({ variant = 'chrome' }: Props) {
  const { choice, setChoice } = useTheme()

  const isSurface = variant === 'surface'

  return (
    <div
      className={`flex items-center gap-0.5 rounded-lg p-0.5 transition-colors ${
        isSurface
          ? 'border border-ink-200 bg-surface shadow-2xs'
          : 'bg-chrome-surface'
      }`}
    >
      {OPTIONS.map(({ value, icon: Icon, label }) => {
        const isSelected = choice === value
        const activeClass = isSurface
          ? 'bg-brand-50 text-brand-600 font-semibold dark:bg-brand-900/40 dark:text-brand-300'
          : 'bg-brand-500/20 text-brand-300'
        const inactiveClass = isSurface
          ? 'text-ink-500 hover:bg-ink-100 hover:text-ink-900'
          : 'text-chrome-text-secondary hover:text-chrome-text-primary'

        return (
          <button
            key={value}
            onClick={() => setChoice(value)}
            title={label}
            aria-label={label}
            aria-pressed={isSelected}
            className={`cursor-pointer flex h-6 w-6 items-center justify-center rounded-md transition-colors ${
              isSelected ? activeClass : inactiveClass
            }`}
          >
            <Icon size={13} />
          </button>
        )
      })}
    </div>
  )
}
