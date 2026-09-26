import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, hasToken, onUnauthorized, setToken, type Build, type Me, type Session } from './api'

interface AuthState {
  me: Me | null
  build: Build | null
  ready: boolean
  backendDown: boolean
  signIn: (session: Session) => Promise<void>
  signOut: () => void
  can: (action: string) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [build, setBuild] = useState<Build | null>(null)
  const [ready, setReady] = useState(false)
  const [backendDown, setBackendDown] = useState(false)

  useEffect(() => {
    onUnauthorized(() => setMe(null))
    ;(async () => {
      try {
        setBuild((await api.health()).build)
      } catch {
        setBackendDown(true)
        setReady(true)
        return
      }
      if (hasToken()) {
        try {
          setMe(await api.me())
        } catch {
          setToken(null)
        }
      }
      setReady(true)
    })()
  }, [])

  const signIn = useCallback(async (session: Session) => {
    setToken(session.access_token)
    setMe(await api.me())
  }, [])

  const signOut = useCallback(() => {
    setToken(null)
    setMe(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({ me, build, ready, backendDown, signIn, signOut, can: (a) => !!me?.permissions.includes(a) }),
    [me, build, ready, backendDown, signIn, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
