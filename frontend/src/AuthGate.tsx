
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
  type FormEvent,
} from 'react'
import {
  Orbit,
  LockKeyhole,
  Mail,
  Eye,
  EyeOff,
  Loader2,
  ShieldCheck,
  AlertCircle,
  LogIn,
} from 'lucide-react'

const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const TOKEN_KEY = 'orbit_access_token'

interface User {
  user_id: number | string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

interface AuthContextType {
  user: User | null
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used inside AuthGate')
  }

  return context
}

interface AuthGateProps {
  children: ReactNode
}

export default function AuthGate({ children }: AuthGateProps) {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true

    async function verifySession() {
      const token = localStorage.getItem(TOKEN_KEY)

      if (!token) {
        if (mounted) setChecking(false)
        return
      }

      try {
        const response = await fetch(`${API}/api/auth/me`, {
          headers: {
            Accept: 'application/json',
            Authorization: `Bearer ${token}`,
          },
          cache: 'no-store',
        })

        if (!response.ok) {
          throw new Error('Session expired')
        }

        const data = await response.json()

        if (mounted) {
          setUser(data.user)
        }
      } catch {
        localStorage.removeItem(TOKEN_KEY)
      } finally {
        if (mounted) setChecking(false)
      }
    }

    void verifySession()

    return () => {
      mounted = false
    }
  }, [])

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
    setPassword('')
    setEmail('')
    setError('')
  }

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!email.trim() || !password) {
      setError('Please enter your email and password.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await fetch(`${API}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      })

      const data = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : `Login failed. HTTP ${response.status}`,
        )
      }

      if (!data.access_token) {
        throw new Error('Authentication token was not returned.')
      }

      localStorage.setItem(TOKEN_KEY, data.access_token)

      // Verify the newly received token before opening the dashboard.
      const profileResponse = await fetch(`${API}/api/auth/me`, {
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${data.access_token}`,
        },
        cache: 'no-store',
      })

      const profileData = await profileResponse.json().catch(() => ({}))

      if (!profileResponse.ok || !profileData.user) {
        localStorage.removeItem(TOKEN_KEY)
        throw new Error('Unable to verify your account. Please login again.')
      }

      setUser(profileData.user)
      setPassword('')
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to connect to the authentication server.',
      )
    } finally {
      setLoading(false)
    }
  }

  if (checking) {
    return (
      <div style={styles.loadingScreen}>
        <Loader2 size={32} className="spin" />
        <p>Verifying your ORBIT session...</p>
      </div>
    )
  }

  if (user) {
    return (
      <AuthContext.Provider value={{ user, logout }}>
        {children}
      </AuthContext.Provider>
    )
  }

  return (
    <div style={styles.page}>
      <div style={styles.glow} />

      <div style={styles.loginCard}>
        <div style={styles.brand}>
          <div style={styles.logo}>
            <Orbit size={30} />
          </div>
          <div>
            <h1>ORBIT<span style={{ color: '#a78bfa' }}>.</span></h1>
            <p>INTELLIGENCE WORKSPACE</p>
          </div>
        </div>

        <div style={styles.heading}>
          <div style={styles.iconBox}>
            <LockKeyhole size={23} />
          </div>
          <h2>Welcome back.</h2>
          <p>Sign in to access your analytics workspace.</p>
        </div>

        <form onSubmit={handleLogin}>
          <label style={styles.label}>EMAIL ADDRESS</label>

          <div style={styles.inputWrapper}>
            <Mail size={18} style={styles.inputIcon} />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              autoComplete="username"
              required
              style={styles.input}
            />
          </div>

          <label style={styles.label}>PASSWORD</label>

          <div style={styles.inputWrapper}>
            <LockKeyhole size={18} style={styles.inputIcon} />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
              required
              style={styles.input}
            />

            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              style={styles.eyeButton}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>

          {error && (
            <div style={styles.error}>
              <AlertCircle size={17} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              ...styles.submit,
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? (
              <>
                <Loader2 size={19} className="spin" />
                Authenticating...
              </>
            ) : (
              <>
                <LogIn size={19} />
                Sign in to ORBIT
              </>
            )}
          </button>
        </form>

        <div style={styles.security}>
          <ShieldCheck size={16} />
          Secure JWT authentication
        </div>

        <div style={styles.footer}>
          ORBIT ANALYTICS AGENT · POWERED BY AI
        </div>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#080c17',
    color: '#f8fafc',
    padding: '24px',
    fontFamily: 'Inter, system-ui, sans-serif',
    position: 'relative',
    overflow: 'hidden',
  },
  glow: {
    position: 'absolute',
    width: '500px',
    height: '500px',
    background: 'rgba(124, 92, 255, 0.13)',
    filter: 'blur(110px)',
    borderRadius: '50%',
    top: '10%',
    left: '35%',
    pointerEvents: 'none',
  },
  loginCard: {
    position: 'relative',
    width: '100%',
    maxWidth: '440px',
    padding: '42px',
    background: 'rgba(17, 25, 42, 0.96)',
    border: '1px solid #29334d',
    borderRadius: '20px',
    boxShadow: '0 25px 80px rgba(0,0,0,0.4)',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: '13px',
    marginBottom: '44px',
  },
  logo: {
    width: '52px',
    height: '52px',
    display: 'grid',
    placeItems: 'center',
    background: '#29254d',
    color: '#b7aaff',
    borderRadius: '14px',
  },
  heading: {
    marginBottom: '30px',
  },
  iconBox: {
    width: '42px',
    height: '42px',
    display: 'grid',
    placeItems: 'center',
    color: '#b7aaff',
    background: '#252344',
    borderRadius: '12px',
    marginBottom: '18px',
  },
  label: {
    display: 'block',
    fontSize: '11px',
    letterSpacing: '1.2px',
    fontWeight: 700,
    color: '#aab4cc',
    marginBottom: '10px',
  },
  inputWrapper: {
    height: '52px',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    border: '1px solid #34415d',
    borderRadius: '10px',
    background: '#0b1220',
    padding: '0 14px',
    marginBottom: '23px',
  },
  inputIcon: {
    color: '#929db8',
    flexShrink: 0,
  },
  input: {
    flex: 1,
    minWidth: 0,
    height: '100%',
    background: 'transparent',
    color: '#fff',
    border: 'none',
    outline: 'none',
    fontSize: '14px',
  },
  eyeButton: {
    background: 'transparent',
    border: 'none',
    color: '#aab4cc',
    cursor: 'pointer',
    display: 'grid',
    placeItems: 'center',
  },
  submit: {
    width: '100%',
    height: '53px',
    border: 'none',
    borderRadius: '10px',
    background: 'linear-gradient(100deg, #7160d9, #8d75ed)',
    color: '#fff',
    fontWeight: 700,
    fontSize: '14px',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: '10px',
    cursor: 'pointer',
    marginTop: '10px',
  },
  error: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '9px',
    color: '#fca5a5',
    background: 'rgba(127, 29, 29, 0.2)',
    border: '1px solid rgba(248, 113, 113, 0.3)',
    padding: '12px',
    borderRadius: '9px',
    fontSize: '13px',
    marginBottom: '14px',
  },
  security: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: '8px',
    color: '#9da9c3',
    fontSize: '12px',
    marginTop: '25px',
  },
  footer: {
    textAlign: 'center',
    color: '#68748f',
    fontSize: '9px',
    letterSpacing: '1.2px',
    marginTop: '38px',
  },
  loadingScreen: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '14px',
    background: '#080c17',
    color: '#b7aaff',
  },
}
