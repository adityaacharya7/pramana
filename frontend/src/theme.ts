export type Theme = 'light' | 'dark'
const KEY = 'pramana.theme'

export function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

export function effectiveTheme(): Theme {
  return storedTheme() ?? (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
}

export function applyTheme(theme: Theme | null) {
  const root = document.documentElement
  if (theme) root.dataset.theme = theme
  else delete root.dataset.theme
  try {
    if (theme) localStorage.setItem(KEY, theme)
    else localStorage.removeItem(KEY)
  } catch {
    // storage unavailable: the choice lasts for this page only
  }
}
