import { createContext, useContext, useEffect, useRef, useState } from 'react'

export type Theme = 'light' | 'dark'

interface ThemeContextValue {
  theme: Theme
  toggle: () => void
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'light',
  toggle: () => {},
})

const STORAGE_KEY = 'nexusrag-theme'

function getInitialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  // 未有用户偏好时跟随系统
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  // 用户是否显式切换过主题：未显式选择时实时跟随系统偏好变化
  // （此前首次挂载即写 localStorage，导致系统偏好永远不再生效）
  const userPinned = useRef<boolean>(Boolean(localStorage.getItem(STORAGE_KEY)))

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    // color-scheme 让原生控件（滚动条/输入框）随主题变化
    document.documentElement.style.colorScheme = theme
    // 仅显式选择过的偏好才持久化
    if (userPinned.current) localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggle = () => {
    userPinned.current = true
    setTheme(t => (t === 'dark' ? 'light' : 'dark'))
  }

  // 系统深浅色切换时跟随（用户点过切换按钮后以用户选择为准）
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => {
      if (!userPinned.current) setTheme(e.matches ? 'dark' : 'light')
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const value = { theme, toggle }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => useContext(ThemeContext)
