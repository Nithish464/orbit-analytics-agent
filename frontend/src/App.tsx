import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  BarChart3,
  Bot,
  Check,
  ChevronDown,
  Clock3,
  Columns3,
  Copy,
  Database,
  Download,
  Gauge,
  Layers3,
  Loader2,
  LockKeyhole,
  PanelLeftClose,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Table2,
  Terminal,
  TrendingUp,
  WandSparkles,
  Zap,
  CircleHelp,
} from 'lucide-react'
import { useAuth } from './AuthGate'

const AnalyticsChart = lazy(() => import('./components/AnalyticsChart'))
const RagPanel = lazy(() => import('./components/RagPanel'))

const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

type Page = 'Analytics studio' | 'Data sources' | 'SQL explorer' | 'Performance' | 'Document intelligence'
type ResultTab = 'visual' | 'table' | 'sql'
type Health = 'checking' | 'online' | 'offline'

interface AgentStep {
  name: string
  status: string
  detail: string
}

interface ChartData {
  type: string
  xKey: string
  yKey: string
  label: string
  data: Record<string, string | number>[]
}

interface AnalysisResult {
  question: string
  answer: string
  sql: string
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  chart: ChartData | null
  steps: AgentStep[]
  duration_ms: number
  mode: string

  // Performance metrics returned by the upgraded backend.
  planner_duration_ms?: number
  builder_duration_ms?: number
  critic_duration_ms?: number
  sql_duration_ms?: number
  ai_duration_ms?: number
  chart_duration_ms?: number
  cache_hit?: boolean
}

interface HistoryItem {
  question: string
}

interface SchemaTable {
  table: string
  columns: string[]
}

interface PerformanceTrendItem {
  timestamp: string
  status: string
  api_duration_ms: number
  sql_duration_ms: number
  ai_duration_ms: number
  cache_hit: boolean | null
  row_count: number
}

interface PerformanceSnapshot {
  requests_total: number
  successful_requests: number
  failed_requests: number
  success_rate: number
  avg_api_duration_ms: number
  p95_api_duration_ms: number
  avg_sql_duration_ms: number
  avg_ai_duration_ms: number
  cache_hits: number
  cache_misses: number
  cache_hit_rate: number
  sample_size: number
  max_sample_size: number
  trend: PerformanceTrendItem[]
}

const examples = [
  {
    icon: '↗',
    title: 'Revenue overview',
    question: 'What is our total revenue?',
    description: 'Get a pulse on business performance',
  },
  {
    icon: '▥',
    title: 'Monthly performance',
    question: 'Show monthly revenue for 2024',
    description: 'Explore revenue trends over time',
  },
  {
    icon: '✳',
    title: 'Top products',
    question: 'Which are the top 5 products by revenue?',
    description: 'Find your highest-value products',
  },
  {
    icon: '⌘',
    title: 'Regional breakdown',
    question: 'Show revenue by region',
    description: 'Compare performance by geography',
  },
]

export default function App() {
  const { user, logout } = useAuth()
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)

  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [health, setHealth] = useState<Health>('checking')

  const [schema, setSchema] = useState<SchemaTable[]>([])
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [tab, setTab] = useState<ResultTab>('visual')
  const [sidebar, setSidebar] = useState(true)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [activeNav, setActiveNav] = useState<Page>('Analytics studio')
  const [schemaLoading, setSchemaLoading] = useState(false)
  const [performance, setPerformance] = useState<PerformanceSnapshot | null>(null)
  const [performanceLoading, setPerformanceLoading] = useState(false)
  const [performanceError, setPerformanceError] = useState('')
  const [performanceUpdatedAt, setPerformanceUpdatedAt] = useState<Date | null>(null)

  useEffect(() => {
    if (!mobileSidebarOpen) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileSidebarOpen(false)
    }

    window.addEventListener('keydown', closeOnEscape)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [mobileSidebarOpen])

  const refreshHistory = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/history`)
      if (!response.ok) return

      const data = await response.json()
      setHistory(Array.isArray(data.items) ? data.items : [])
    } catch {
      // History is optional.
    }
  }, [])

  const refreshSchema = useCallback(async () => {
    setSchemaLoading(true)

    try {
      const response = await fetch(`${API}/api/schema`)

      if (!response.ok) {
        throw new Error('Unable to load database schema.')
      }

      const data = await response.json()
      setSchema(Array.isArray(data.tables) ? data.tables : [])
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to refresh database schema.',
      )
    } finally {
      setSchemaLoading(false)
    }
  }, [])

  const refreshPerformance = useCallback(async (showLoading = true) => {
    if (showLoading) setPerformanceLoading(true)
    setPerformanceError('')

    try {
      const response = await fetch(`${API}/api/performance`, {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(
          typeof body.detail === 'string'
            ? body.detail
            : `Performance API returned HTTP ${response.status}.`,
        )
      }

      const data = await response.json()
      setPerformance({
        requests_total: Number(data.requests_total ?? 0),
        successful_requests: Number(data.successful_requests ?? 0),
        failed_requests: Number(data.failed_requests ?? 0),
        success_rate: Number(data.success_rate ?? 0),
        avg_api_duration_ms: Number(data.average_api_duration_ms ?? 0),
        p95_api_duration_ms: Number(data.p95_api_duration_ms ?? 0),
        avg_sql_duration_ms: Number(data.average_sql_duration_ms ?? 0),
        avg_ai_duration_ms: Number(data.average_ai_duration_ms ?? 0),
        cache_hits: Number(data.cache_hits ?? 0),
        cache_misses: Number(data.cache_misses ?? 0),
        cache_hit_rate: Number(data.cache_hit_rate ?? 0),
        sample_size: Number(data.sample_size ?? 0),
        max_sample_size: Number(data.max_sample_size ?? 500),
        trend: Array.isArray(data.trend) ? data.trend : [],
      })
      setPerformanceUpdatedAt(new Date())
    } catch (err) {
      setPerformanceError(
        err instanceof Error ? err.message : 'Unable to load performance metrics.',
      )
    } finally {
      if (showLoading) setPerformanceLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeNav !== 'Performance') return

    void refreshPerformance()
    const interval = window.setInterval(() => {
      void refreshPerformance(false)
    }, 15000)

    return () => window.clearInterval(interval)
  }, [activeNav, refreshPerformance])

  useEffect(() => {
    let mounted = true

    async function initialize() {
      try {
        const response = await fetch(`${API}/api/health`)
        if (!response.ok) throw new Error('Backend unavailable')

        if (mounted) setHealth('online')
      } catch {
        if (mounted) setHealth('offline')
      }

      try {
        const response = await fetch(`${API}/api/schema`)

        if (response.ok) {
          const data = await response.json()

          if (mounted) {
            setSchema(Array.isArray(data.tables) ? data.tables : [])
          }
        }
      } catch {
        if (mounted) setSchema([])
      }

      if (mounted) await refreshHistory()
    }

    void initialize()

    return () => {
      mounted = false
    }
  }, [refreshHistory])

  const runAnalysis = async (value: string = question) => {
    const cleanQuestion = value.trim()

    if (!cleanQuestion || loading) return

    setQuestion(cleanQuestion)
    setLoading(true)
    setError('')
    setResult(null)
    setActiveNav('Analytics studio')
    setMobileSidebarOpen(false)

    try {
      const response = await fetch(`${API}/api/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ question: cleanQuestion }),
      })

      const data = await response.json()

      if (!response.ok) {
        const message =
          typeof data.detail === 'string'
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail
                  .map((item: { msg?: string }) => item.msg)
                  .join(', ')
              : 'Analysis failed. Please try another question.'

        throw new Error(message)
      }

      setResult(data as AnalysisResult)
      setTab('visual')
      setHealth('online')

      await refreshHistory()
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : 'Unable to connect to the API.'

      setError(message)

      if (
        message.toLowerCase().includes('fetch') ||
        message.toLowerCase().includes('network')
      ) {
        setHealth('offline')
      }
    } finally {
      setLoading(false)
    }
  }

  // Extract a numeric total from the returned database result.
  const totalRevenue = useMemo(() => {
    if (!result?.rows.length) return null

    const firstRow = result.rows[0]

    const totalKeys = [
      'total_revenue',
      'total',
      'sum_revenue',
      'revenue_total',
    ]

    for (const key of totalKeys) {
      const value = firstRow[key]

      if (typeof value === 'number' && Number.isFinite(value)) {
        return value
      }
    }

    // If the query returns individual revenue rows, sum those rows.
    const revenueKey = result.columns.find(
      (column) => column.toLowerCase() === 'revenue',
    )

    if (revenueKey) {
      const values = result.rows
        .map((row) => row[revenueKey])
        .filter(
          (value): value is number =>
            typeof value === 'number' && Number.isFinite(value),
        )

      if (values.length > 0) {
        return values.reduce((sum, value) => sum + value, 0)
      }
    }

    return null
  }, [result])

  const isSingleValue = useMemo(() => {
    if (!result) return false

    return (
      result.rows.length === 1 &&
      (!result.chart || result.chart.data.length <= 1)
    )
  }, [result])

  const exportCSV = () => {
    if (!result || result.rows.length === 0) return

    const escapeCSV = (value: unknown) =>
      `"${String(value ?? '').replace(/"/g, '""')}"`

    const lines = [
      result.columns.map(escapeCSV).join(','),
      ...result.rows.map((row) =>
        result.columns
          .map((column) => escapeCSV(row[column]))
          .join(','),
      ),
    ]

    const blob = new Blob([lines.join('\n')], {
      type: 'text/csv;charset=utf-8;',
    })

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = 'orbit-analysis.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const copySQL = async () => {
    if (!result?.sql) return

    try {
      await navigator.clipboard.writeText(result.sql)
    } catch {
      setError('Unable to copy SQL. Check browser clipboard permissions.')
    }
  }

  const newAnalysis = () => {
    setQuestion('')
    setResult(null)
    setError('')
    setTab('visual')
    setActiveNav('Analytics studio')
    setMobileSidebarOpen(false)
  }

  const selectNavigation = (page: Page) => {
    setActiveNav(page)
    setError('')
    setMobileSidebarOpen(false)

    if (page === 'Analytics studio') {
      newAnalysis()
    }

    if (page === 'Data sources') {
      void refreshSchema()
    }

  }

  const toggleSidebar = () => {
    if (window.matchMedia('(max-width: 760px)').matches) {
      setMobileSidebarOpen((previous) => !previous)
    } else {
      setSidebar((previous) => !previous)
    }
  }

  const uniqueHistory = history.filter(
    (item, index, items) =>
      items.findIndex(
        (candidate) =>
          candidate.question.trim().toLowerCase() ===
          item.question.trim().toLowerCase(),
      ) === index,
  )

  return (
    <div className="shell">
      <aside
        className={`sidebar ${!sidebar ? 'collapsed' : ''} ${
          mobileSidebarOpen ? 'mobile-open' : ''
        }`}
      >
        <div className="brand">
          <div className="mark">
            <Orbit />
          </div>

          {(sidebar || mobileSidebarOpen) && (
            <div>
              <b>ORBIT<span>.</span></b>
              <small>INTELLIGENCE WORKSPACE</small>
            </div>
          )}
        </div>

        <div className="workspace">
          <div className="avatar">N</div>

          {(sidebar || mobileSidebarOpen) && (
            <>
              <span>
                <b>Northstar Retail</b>
                <small>Free workspace</small>
              </span>
              <ChevronDown size={14} />
            </>
          )}
        </div>

        {(sidebar || mobileSidebarOpen) && (
          <>
            <label>WORKSPACE</label>

            <NavButton
              icon={<BarChart3 />}
              name="Analytics studio"
              active={activeNav === 'Analytics studio'}
              onClick={() => selectNavigation('Analytics studio')}
            />

            <NavButton
              icon={<Database />}
              name="Data sources"
              active={activeNav === 'Data sources'}
              onClick={() => selectNavigation('Data sources')}
            />

            <NavButton
              icon={<Terminal />}
              name="SQL explorer"
              active={activeNav === 'SQL explorer'}
              onClick={() => selectNavigation('SQL explorer')}
            />

            <NavButton
              icon={<Gauge />}
              name="Performance"
              active={activeNav === 'Performance'}
              onClick={() => selectNavigation('Performance')}
            />

            <NavButton
              icon={<Sparkles />}
              name="Document intelligence"
              active={activeNav === 'Document intelligence'}
              onClick={() => selectNavigation('Document intelligence')}
            />

            <button className="nav" disabled title="Coming soon">
              <Layers3 />
              Agent workflows
              <small>SOON</small>
            </button>

            <div className="side-rule" />

            <label>RECENT ANALYSES</label>

            {uniqueHistory.slice(0, 5).map((item, index) => (
              <button
                className="recent"
                key={`${item.question}-${index}`}
                title={item.question}
                onClick={() => void runAnalysis(item.question)}
              >
                <Clock3 />
                <span>{item.question}</span>
              </button>
            ))}

            {uniqueHistory.length === 0 && (
              <div className="recent">
                <Clock3 />
                No recent analyses
              </div>
            )}
          </>
        )}

        <div className="side-bottom">
          <div className="environment">
            <Zap />
            {(sidebar || mobileSidebarOpen) && (
              <span>
                <b>Demo environment</b>
                <small>Local synthetic dataset</small>
              </span>
            )}
          </div>

          <div className="profile">
            <div className="avatar">NK</div>
            {(sidebar || mobileSidebarOpen) && (
              <span>
                <b>Analyst workspace</b>
                <small>Personal account</small>
              </span>
            )}
          </div>
        </div>
      </aside>

      {mobileSidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      <main>
        <header>
          <div className="crumb">
            <button onClick={toggleSidebar} title="Toggle sidebar">
              <PanelLeftClose />
            </button>

            Workspace
            <i>/</i>
            <b>{activeNav}</b>
          </div>

          <div className="topright">
            <span className={`connection ${health}`}>
              <i />
              {health === 'online'
                ? 'API connected'
                : health === 'offline'
                  ? 'API offline'
                  : 'Connecting'}
            </span>

            <CircleHelp />
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                className="avatar"
                title="Open account menu"
                aria-label="Open account menu"
                aria-expanded={profileMenuOpen}
                onClick={() => setProfileMenuOpen((open) => !open)}
                style={{ border: 'none', cursor: 'pointer' }}
              >
                {user?.email?.slice(0, 2).toUpperCase() ?? "OR"}
              </button>

              {profileMenuOpen && (
                <div
                  role="menu"
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 12px)',
                    right: 0,
                    zIndex: 1000,
                    width: 230,
                    padding: 12,
                    border: '1px solid #29344a',
                    borderRadius: 12,
                    background: '#111827',
                    boxShadow: '0 16px 40px rgba(0,0,0,0.4)',
                  }}
                >
                  <div style={{ padding: '8px 9px 12px', borderBottom: '1px solid #29344a', marginBottom: 8 }}>
                    <div style={{ color: '#f8fafc', fontSize: 13, fontWeight: 600 }}>Signed in</div>
                    <div style={{ color: '#94a3b8', fontSize: 11, marginTop: 4, overflowWrap: 'anywhere' }}>
                      {user?.email ?? 'ORBIT account'}
                    </div>
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={logout}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 9,
                      padding: '10px 9px',
                      border: 0,
                      borderRadius: 8,
                      background: 'transparent',
                      color: '#fca5a5',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: 13,
                    }}
                  >
                    <LockKeyhole size={15} />
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="content">
          {activeNav === 'Document intelligence' ? (
            <Suspense fallback={<div className="empty loading"><Loader2 className="spin" /><h3>Loading Document Intelligence</h3><p>Preparing the RAG workspace...</p></div>}>
              <RagPanel />
            </Suspense>
          ) : activeNav === 'Performance' ? (
            <PerformanceDashboard
              data={performance}
              loading={performanceLoading}
              error={performanceError}
              updatedAt={performanceUpdatedAt}
              onRefresh={() => void refreshPerformance()}
            />
          ) : activeNav === 'Data sources' ? (
            <DataSourcesPage
              schema={schema}
              health={health}
              loading={schemaLoading}
              onRefresh={() => void refreshSchema()}
            />
          ) : activeNav === 'SQL explorer' ? (
            <SqlExplorerPage
              result={result}
              onCopy={() => void copySQL()}
              onNewAnalysis={() => selectNavigation('Analytics studio')}
            />
          ) : (
            <>
              <div className="heading">
                <div>
                  <label>
                    <i />
                    INTELLIGENCE / OVERVIEW
                  </label>

                  <h1>
                    Good evening, <em>Analyst.</em>
                  </h1>

                  <p>
                    Ask your data anything. Turn questions into decisions.
                  </p>
                </div>

                <div className="live">
                  <span /> LIVE DEMO
                  <small>NORTHSTAR RETAIL · SYNTHETIC DATA</small>
                </div>
              </div>

              <section className="ask">
                <div className="ask-title">
                  <div className="spark">
                    <Sparkles />
                  </div>

                  <div>
                    <b>Ask ORBIT</b>
                    <small>Your autonomous data analyst</small>
                  </div>

                  <span className="mode">
                    ● DETERMINISTIC AGENT MODE
                  </span>
                </div>

                <div className="prompt">
                  <textarea
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault()
                        void runAnalysis()
                      }
                    }}
                    placeholder="Ask a question about your business data..."
                    aria-label="Analytics question"
                  />

                  <button
                    disabled={!question.trim() || loading}
                    onClick={() => void runAnalysis()}
                  >
                    {loading ? (
                      <>
                        <Loader2 className="spin" />
                        Analyzing
                      </>
                    ) : (
                      <>
                        Run analysis
                        <ArrowUpRight />
                      </>
                    )}
                  </button>
                </div>

                <div className="ask-foot">
                  <span>
                    <LockKeyhole />
                    Read-only query execution
                  </span>
                  <span>Enter to run · Shift + Enter for new line</span>
                </div>

                <div className="examples">
                  {examples.map((item) => (
                    <button
                      key={item.title}
                      onClick={() => void runAnalysis(item.question)}
                      disabled={loading}
                    >
                      <i>{item.icon}</i>
                      <span>
                        <b>{item.title}</b>
                        <small>{item.description}</small>
                      </span>
                      <ArrowUpRight />
                    </button>
                  ))}
                </div>
              </section>

              {error && (
                <div className="error">
                  <AlertCircle />
                  {error}
                </div>
              )}

              <div className="metrics">
                <Metric
                  icon={<TrendingUp />}
                  label="TOTAL REVENUE"
                  value={totalRevenue !== null ? money(totalRevenue) : '—'}
                  note="Calculated from returned data"
                />

                <Metric
                  icon={<Database />}
                  label="RESULT ROWS"
                  value={result ? String(result.row_count) : '—'}
                  note="Latest analysis"
                />

                <Metric
                  icon={<Gauge />}
                  label="QUERY LATENCY"
                  value={result ? `${result.duration_ms} ms` : '—'}
                  note="Backend execution time"
                />

                <Metric
                  icon={<Activity />}
                  label="AGENT STEPS"
                  value={result ? String(result.steps.length) : '5'}
                  note="Planner to analyst"
                />
              </div>

              <div className="section-head">
                <div>
                  <label>YOUR WORKSPACE</label>
                  <h2>{result ? 'Analysis results' : 'Start with an insight'}</h2>
                </div>

                <div>
                  {result && (
                    <button className="outline" onClick={exportCSV}>
                      <Download />
                      Export CSV
                    </button>
                  )}

                  <button className="outline" onClick={newAnalysis}>
                    <Plus />
                    New analysis
                  </button>
                </div>
              </div>

              {loading ? (
                <div className="empty loading">
                  <Loader2 className="spin" />
                  <h3>ORBIT is analyzing your question</h3>
                  <p>Planning · SQL validation · Query execution</p>
                </div>
              ) : result ? (
                <div className="results">
                  <section className="panel">
                    <div className="panel-head">
                      <b>
                        <Check />
                        INSIGHT GENERATED
                        <small>· {result.duration_ms} ms</small>
                      </b>
                      <span>DEMO DATA</span>
                    </div>

                    <div className="answer">
                      <WandSparkles />
                      <div>
                        <h3>{result.answer}</h3>
                        <p>
                          Generated from query results. Validate
                          business-critical decisions against your source
                          systems.
                        </p>
                      </div>
                    </div>

                    <div className="tabs">
                      <button
                        className={tab === 'visual' ? 'chosen' : ''}
                        onClick={() => setTab('visual')}
                      >
                        <BarChart3 /> Visual
                      </button>

                      <button
                        className={tab === 'table' ? 'chosen' : ''}
                        onClick={() => setTab('table')}
                      >
                        <Table2 /> Data table
                      </button>

                      <button
                        className={tab === 'sql' ? 'chosen' : ''}
                        onClick={() => setTab('sql')}
                      >
                        <Terminal /> SQL
                      </button>
                    </div>

                    <div className="tabbody">
                      {tab === 'visual' ? (
                        result.chart && result.chart.data.length > 0 ? (
                          <Suspense
                            fallback={
                              <div className="chart-wrap" aria-live="polite">
                                <div className="chart-title">
                                  <b>Loading visualization...</b>
                                  <small>PLEASE WAIT</small>
                                </div>
                                <div className="no-chart">
                                  <Loader2 className="spin" />
                                  <span>Loading chart module</span>
                                </div>
                              </div>
                            }
                          >
                            <AnalyticsChart chart={result.chart} />
                          </Suspense>
                        ) : totalRevenue !== null ? (
                          <RevenueVisualization
                            totalRevenue={totalRevenue}
                            rowCount={result.row_count}
                          />
                        ) : (
                          <div className="no-chart">
                            <BarChart3 />
                            <span>
                              No visualization available for this result.
                            </span>
                          </div>
                        )
                      ) : tab === 'table' ? (
                        <DataTable result={result} />
                      ) : (
                        <div className="sql">
                          <div>
                            <span>● SQL VALIDATED</span>
                            <button onClick={() => void copySQL()}>
                              <Copy /> Copy
                            </button>
                          </div>

                          <pre>{result.sql || '-- No SQL returned'}</pre>

                          <small>
                            <ShieldCheck />
                            Read-only query · validated before execution
                          </small>
                        </div>
                      )}
                    </div>
                  </section>

                  <div className="stack">
                    <section className="panel">
                      <div className="panel-head">
                        <b><Activity /> AGENT TRACE</b>
                        <span className="done">COMPLETED</span>
                      </div>

                      <div className="trace">
                        {result.steps.map((step, index) => (
                          <div className="step" key={`${step.name}-${index}`}>
                            <i><Check /></i>
                            <div>
                              <b>{step.name}</b>
                              <small>{step.detail}</small>
                            </div>
                            {index < result.steps.length - 1 && <u />}
                          </div>
                        ))}
                      </div>
                    </section>

                    <PerformancePanel result={result} />

                    <section className="panel">
                      <div className="panel-head">
                        <b><Database /> DATA CONTEXT</b>
                        <span>SCHEMA</span>
                      </div>

                      <div className="catalog">
                        <button onClick={() => selectNavigation('Data sources')}>
                          <b><Table2 /> INSPECT TABLES</b>
                          <ArrowUpRight />
                        </button>

                        <p>
                          ORBIT uses the connected read-only schema to plan
                          and validate analytical queries.
                        </p>

                        <small className="dbstatus">
                          ● SQLite · {schema.length} tables discovered
                        </small>
                      </div>
                    </section>
                  </div>
                </div>
              ) : (
                <div className="empty">
                  <div className="empty-art">
                    <div />
                    <Bot />
                  </div>

                  <h3>Your next insight is one question away.</h3>

                  <p>
                    ORBIT plans the analysis, validates a safe query, and
                    turns results into a clear business narrative.
                  </p>

                  <div className="capabilities">
                    <span><ShieldCheck /> SQL safety</span>
                    <span><Zap /> Agent workflow</span>
                    <span><BarChart3 /> Visual insights</span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
/* REVENUE VISUALIZATION */
function RevenueVisualization({
  totalRevenue,
  rowCount,
}: {
  totalRevenue: number
  rowCount: number
}) {
  return (
    <div className="revenue-visual">
      <div className="revenue-visual-top">
        <span><TrendingUp /> REVENUE PERFORMANCE</span>
        <span className="verified"><Check /> DATABASE RESULT</span>
      </div>

      <div className="revenue-hero">
        <small>TOTAL REVENUE</small>
        <strong>{money(totalRevenue)}</strong>
        <p>
          Revenue calculated from the returned database results.
        </p>
      </div>

      <div className="revenue-visual-bar">
        <div />
      </div>

      <div className="revenue-visual-bottom">
        <span>{rowCount} result rows</span>
        <span>Returned database total</span>
      </div>
    </div>
  )
}

/* PERFORMANCE BREAKDOWN */
function PerformancePanel({
  result,
}: {
  result: AnalysisResult
}) {
  const metrics = [
    {
      label: 'Planner',
      value: result.planner_duration_ms,
      description: 'Question planning',
    },
    {
      label: 'SQL Builder',
      value: result.builder_duration_ms,
      description: 'SQL generation',
    },
    {
      label: 'SQL Critic',
      value: result.critic_duration_ms,
      description: 'Query validation',
    },
    {
      label: 'Database',
      value: result.sql_duration_ms,
      description: 'Query execution',
    },
    {
      label: 'AI Analyst',
      value: result.ai_duration_ms,
      description: 'Business insight generation',
    },
    {
      label: 'Chart',
      value: result.chart_duration_ms,
      description: 'Visualization generation',
    },
  ]

  const availableMetrics = metrics.filter(
    (metric) =>
      typeof metric.value === 'number' &&
      Number.isFinite(metric.value),
  )

  return (
    <section className="panel performance-panel">
      <div className="panel-head">
        <b>
          <Gauge />
          PERFORMANCE BREAKDOWN
        </b>

        <span className="done">
          {result.cache_hit === true
            ? 'CACHE HIT'
            : result.cache_hit === false
              ? 'CACHE MISS'
              : 'EXECUTION'}
        </span>
      </div>

      <div className="performance-summary">
        <div>
          <small>TOTAL EXECUTION TIME</small>
          <strong>{formatDuration(result.duration_ms)}</strong>
        </div>

        <div>
          <small>AI CACHE</small>
          <strong>
            {result.cache_hit === true
              ? 'HIT'
              : result.cache_hit === false
                ? 'MISS'
                : 'N/A'}
          </strong>
        </div>
      </div>

      <div className="performance-list">
        {availableMetrics.length > 0 ? (
          availableMetrics.map((metric) => (
            <div className="performance-item" key={metric.label}>
              <div className="performance-item-info">
                <span>{metric.label}</span>
                <small>{metric.description}</small>
              </div>

              <strong>
                {formatDuration(metric.value)}
              </strong>
            </div>
          ))
        ) : (
          <div className="performance-empty">
            <Clock3 />
            <span>
              Detailed timing metrics are not available from the backend.
            </span>
          </div>
        )}
      </div>

      <div className="performance-footer">
        <span>
          <Activity />
          {availableMetrics.length} timing metrics received
        </span>

        <span>
          Mode: {result.mode || 'Standard'}
        </span>
      </div>
    </section>
  )
}

/* AGGREGATE PERFORMANCE DASHBOARD */
function PerformanceDashboard({
  data,
  loading,
  error,
  updatedAt,
  onRefresh,
}: {
  data: PerformanceSnapshot | null
  loading: boolean
  error: string
  updatedAt: Date | null
  onRefresh: () => void
}) {
  const trend = data?.trend ?? []
  const maxLatency = Math.max(
    1,
    ...trend.map((item) => Number(item.api_duration_ms) || 0),
  )
  const cacheTotal = (data?.cache_hits ?? 0) + (data?.cache_misses ?? 0)
  const hitPercent = cacheTotal > 0
    ? Math.min(100, Math.max(0, (data?.cache_hits ?? 0) / cacheTotal * 100))
    : 0

  return (
    <>
      <div className="heading">
        <div>
          <label><i /> INTELLIGENCE / SYSTEM PERFORMANCE</label>
          <h1>Performance <em>dashboard.</em></h1>
          <p>Monitor API latency, database execution, AI response time, and cache activity.</p>
        </div>
        <div className="live">
          <span /> LIVE METRICS
          <small>{updatedAt ? `UPDATED ${updatedAt.toLocaleTimeString()}` : 'WAITING FOR DATA'}</small>
        </div>
      </div>

      {error && (
        <div className="error">
          <AlertCircle />
          <span>{error} Make sure the backend exposes GET /api/performance.</span>
        </div>
      )}

      <div className="section-head performance-page-head">
        <div>
          <label>RUNTIME OVERVIEW</label>
          <h2>System health and latency</h2>
        </div>
        <div>
          <span className="performance-auto-refresh">AUTO REFRESH · 15 SEC</span>
          <button className="outline" onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 className="spin" /> : <RefreshCw />}
            {loading ? 'Refreshing...' : 'Refresh now'}
          </button>
        </div>
      </div>

      {loading && !data ? (
        <div className="empty loading">
          <Loader2 className="spin" />
          <h3>Loading performance metrics</h3>
          <p>Fetching aggregate request and latency statistics.</p>
        </div>
      ) : data ? (
        <>
          <div className="metrics performance-kpis">
            <Metric icon={<Activity />} label="TOTAL REQUESTS" value={String(data.requests_total)} note={`${data.sample_size} samples retained`} />
            <Metric icon={<ShieldCheck />} label="SUCCESS RATE" value={`${data.success_rate.toFixed(1)}%`} note={`${data.successful_requests} successful · ${data.failed_requests} failed`} />
            <Metric icon={<Gauge />} label="AVG API LATENCY" value={formatDuration(data.avg_api_duration_ms)} note="Average request duration" />
            <Metric icon={<Clock3 />} label="P95 API LATENCY" value={formatDuration(data.p95_api_duration_ms)} note="95th percentile request duration" />
          </div>

          <div className="performance-detail-grid">
            <section className="panel performance-detail-card">
              <div className="panel-head">
                <b><Activity /> LATENCY BREAKDOWN</b>
                <span>AVERAGE</span>
              </div>
              <div className="performance-latency-list">
                <LatencyBar label="API" value={data.avg_api_duration_ms} max={Math.max(data.avg_api_duration_ms, data.avg_sql_duration_ms, data.avg_ai_duration_ms, 1)} />
                <LatencyBar label="Database / SQL" value={data.avg_sql_duration_ms} max={Math.max(data.avg_api_duration_ms, data.avg_sql_duration_ms, data.avg_ai_duration_ms, 1)} />
                <LatencyBar label="AI analyst" value={data.avg_ai_duration_ms} max={Math.max(data.avg_api_duration_ms, data.avg_sql_duration_ms, data.avg_ai_duration_ms, 1)} />
              </div>
              <div className="performance-card-note">Timings are reported by the backend performance collector.</div>
            </section>

            <section className="panel performance-detail-card">
              <div className="panel-head">
                <b><Zap /> CACHE PERFORMANCE</b>
                <span>{cacheTotal} EVENTS</span>
              </div>
              <div className="performance-cache-rate">
                <strong>{data.cache_hit_rate.toFixed(1)}%</strong>
                <span>Cache hit rate</span>
              </div>
              <div className="performance-cache-track">
                <div style={{ width: `${hitPercent}%` }} />
              </div>
              <div className="performance-cache-stats">
                <div><i className="cache-hit-dot" /><span>Hits</span><b>{data.cache_hits}</b></div>
                <div><i className="cache-miss-dot" /><span>Misses</span><b>{data.cache_misses}</b></div>
              </div>
              <div className="performance-card-note">Only accepted AI insight cache events are counted.</div>
            </section>
          </div>

          <section className="panel performance-trend-panel">
            <div className="panel-head">
              <b><TrendingUp /> RECENT REQUEST LATENCY</b>
              <span>LAST {trend.length} REQUESTS</span>
            </div>
            {trend.length > 0 ? (
              <div className="performance-trend-list">
                {trend.map((item, index) => {
                  const width = Math.max(2, (Math.max(0, Number(item.api_duration_ms) || 0) / maxLatency) * 100)
                  const date = new Date(item.timestamp)
                  return (
                    <div className="performance-trend-row" key={`${item.timestamp}-${index}`}>
                      <div className="performance-trend-meta">
                        <span>#{index + 1} · {Number.isNaN(date.getTime()) ? item.timestamp : date.toLocaleTimeString()}</span>
                        <small>{item.status} · {item.row_count} rows</small>
                      </div>
                      <div className="performance-trend-track"><div style={{ width: `${width}%` }} /></div>
                      <strong>{formatDuration(item.api_duration_ms)}</strong>
                      <span className={`performance-cache-tag ${item.cache_hit === true ? 'hit' : item.cache_hit === false ? 'miss' : ''}`}>
                        {item.cache_hit === true ? 'HIT' : item.cache_hit === false ? 'MISS' : '—'}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="performance-no-data"><Clock3 /><span>No request samples yet. Run an analysis in Analytics Studio to populate this chart.</span></div>
            )}
          </section>

          <div className="performance-dashboard-foot">
            <span><Database /> Sample window: {data.sample_size} / {data.max_sample_size} requests</span>
            <span>Metrics are in-memory and reset when the backend restarts.</span>
          </div>
        </>
      ) : (
        <div className="empty">
          <Gauge />
          <h3>Performance metrics are not available</h3>
          <p>Check that the backend is running and that GET /api/performance is enabled.</p>
          <button className="outline" onClick={onRefresh}><RefreshCw /> Try again</button>
        </div>
      )}

      <footer>
        <span>ORBIT INTELLIGENCE WORKSPACE · PERFORMANCE</span>
        <span>Auto-refreshes every 15 seconds while this page is open.</span>
      </footer>
    </>
  )
}

function LatencyBar({ label, value, max }: { label: string; value: number; max: number }) {
  const width = max > 0 ? Math.min(100, Math.max(0, value / max * 100)) : 0
  return (
    <div className="performance-latency-item">
      <div><span>{label}</span><strong>{formatDuration(value)}</strong></div>
      <div className="performance-latency-track"><div style={{ width: `${width}%` }} /></div>
    </div>
  )
}

/* NAVIGATION BUTTON */
function NavButton({
  icon,
  name,
  active,
  onClick,
}: {
  icon: ReactNode
  name: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      className={`nav ${active ? 'active' : ''}`}
      onClick={onClick}
    >
      {icon}
      {name}
      {active && <i />}
    </button>
  )
}

/* DATA SOURCES PAGE */
function DataSourcesPage({
  schema,
  health,
  loading,
  onRefresh,
}: {
  schema: SchemaTable[]
  health: Health
  loading: boolean
  onRefresh: () => void
}) {
  const [selectedTable, setSelectedTable] = useState('')

  useEffect(() => {
    if (
      schema.length > 0 &&
      !schema.some((table) => table.table === selectedTable)
    ) {
      setSelectedTable(schema[0].table)
    }
  }, [schema, selectedTable])

  const totalColumns = schema.reduce(
    (sum, table) =>
      sum + (Array.isArray(table.columns) ? table.columns.length : 0),
    0,
  )

  const currentTable = schema.find(
    (table) => table.table === selectedTable,
  )

  return (
    <>
      <div className="heading">
        <div>
          <label><i /> INTELLIGENCE / DATA SOURCES</label>
          <h1>Data <em>sources.</em></h1>
          <p>
            Inspect your connected warehouse, database tables, and columns.
          </p>
        </div>

        <div className="live">
          <span />
          {health === 'online'
            ? 'CONNECTED'
            : health === 'offline'
              ? 'OFFLINE'
              : 'CHECKING'}
          <small>LOCAL SQLITE DEMO WAREHOUSE</small>
        </div>
      </div>

      <div className="metrics">
        <Metric
          icon={<Database />}
          label="CONNECTION"
          value={
            health === 'online'
              ? 'Online'
              : health === 'offline'
                ? 'Offline'
                : 'Checking'
          }
          note="Backend health status"
        />

        <Metric
          icon={<Layers3 />}
          label="TABLES"
          value={String(schema.length)}
          note="Tables returned by API"
        />

        <Metric
          icon={<Columns3 />}
          label="COLUMNS"
          value={String(totalColumns)}
          note="Discovered schema fields"
        />

        <Metric
          icon={<ShieldCheck />}
          label="ACCESS MODE"
          value="Read-only"
          note="Analytics query execution"
        />
      </div>

      <div className="section-head">
        <div>
          <label>CONNECTED WAREHOUSE</label>
          <h2>Database schema</h2>
        </div>

        <button
          className="outline"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? <Loader2 className="spin" /> : <RefreshCw />}
          {loading ? 'Refreshing...' : 'Refresh schema'}
        </button>
      </div>

      {schema.length > 0 ? (
        <div className="data-source-grid">
          <div className="source-table-list">
            {schema.map((table) => (
              <button
                key={table.table}
                className={`source-table-item ${
                  selectedTable === table.table ? 'selected' : ''
                }`}
                onClick={() => setSelectedTable(table.table)}
              >
                <Database />

                <span>
                  <b>{table.table}</b>
                  <small>{table.columns.length} columns</small>
                </span>

                <ArrowUpRight />
              </button>
            ))}
          </div>

          <section className="panel source-table-detail">
            {currentTable ? (
              <>
                <div className="panel-head">
                  <b><Table2 /> {currentTable.table}</b>
                  <span>{currentTable.columns.length} COLUMNS</span>
                </div>

                <div className="schema-column-list">
                  {currentTable.columns.map((column) => (
                    <div
                      className="schema-column"
                      key={`${currentTable.table}-${column}`}
                    >
                      <Columns3 />
                      <span>{column}</span>
                      <small>Column</small>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty">
                <Database />
                <p>Select a table to inspect its columns.</p>
              </div>
            )}
          </section>
        </div>
      ) : (
        <div className="empty">
          <Database />
          <h3>No schema information available</h3>
          <p>
            Check that the FastAPI backend is running and /api/schema is
            returning database tables.
          </p>
          <button className="outline" onClick={onRefresh}>
            <RefreshCw /> Retry connection
          </button>
        </div>
      )}

      <footer>
        <span>ORBIT INTELLIGENCE WORKSPACE · DATA SOURCES</span>
        <span>Schema is read from the connected demo backend.</span>
      </footer>
    </>
  )
}

/* SQL EXPLORER PAGE */
function SqlExplorerPage({
  result,
  onCopy,
  onNewAnalysis,
}: {
  result: AnalysisResult | null
  onCopy: () => void
  onNewAnalysis: () => void
}) {
  return (
    <>
      <div className="heading">
        <div>
          <label><i /> INTELLIGENCE / SQL EXPLORER</label>
          <h1>SQL <em>explorer.</em></h1>
          <p>
            Inspect the read-only SQL generated by your latest analysis.
          </p>
        </div>

        <div className="live">
          <span /> READ-ONLY MODE
          <small>APPROVED QUERY OUTPUT</small>
        </div>
      </div>

      <div className="section-head">
        <div>
          <label>QUERY WORKSPACE</label>
          <h2>Latest generated SQL</h2>
        </div>

        {result?.sql && (
          <button className="outline" onClick={onCopy}>
            <Copy /> Copy SQL
          </button>
        )}
      </div>

      {result?.sql ? (
        <section className="panel sql">
          <div>
            <span>● SQL VALIDATED</span>
            <small>
              {result.duration_ms} ms · {result.row_count} rows returned
            </small>
          </div>

          <pre>{result.sql}</pre>

          <small>
            <ShieldCheck />
            Single SELECT · approved schema · read-only connection
          </small>
        </section>
      ) : (
        <div className="empty">
          <Terminal />
          <h3>No SQL query yet</h3>
          <p>
            Run a question in Analytics Studio first. Its generated SQL will
            appear here.
          </p>
          <button className="outline" onClick={onNewAnalysis}>
            <Plus /> Start an analysis
          </button>
        </div>
      )}

      <footer>
        <span>ORBIT INTELLIGENCE WORKSPACE · SQL EXPLORER</span>
        <span>Arbitrary SQL execution is not enabled in this demo.</span>
      </footer>
    </>
  )
}
/* KPI CARD */
function Metric({
  icon,
  label,
  value,
  note,
}: {
  icon: ReactNode
  label: string
  value: string
  note: string
}) {
  return (
    <div className="metric">
      <div>
        {icon}
        <small>{label}</small>
      </div>

      <strong>{value}</strong>
      <p>{note}</p>
    </div>
  )
}

/* DATA TABLE */
function DataTable({ result }: { result: AnalysisResult }) {
  if (!result.columns.length || !result.rows.length) {
    return (
      <div className="empty">
        <Table2 />
        <p>No rows available for this analysis.</p>
      </div>
    )
  }

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {result.columns.map((column) => (
              <th key={column}>{column.replace(/_/g, ' ')}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {result.rows.map((row, index) => (
            <tr key={index}>
              {result.columns.map((column) => {
                const value = row[column]

                const isMoney =
                  typeof value === 'number' &&
                  ['revenue', 'amount', 'value'].some((key) =>
                    column.toLowerCase().includes(key),
                  )

                return (
                  <td key={column}>
                    {isMoney
                      ? money(value as number)
                      : formatValue(value)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* HELPERS */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'

  if (typeof value === 'number') {
    return value.toLocaleString('en-US')
  }

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  return String(value)
}

function money(value: number): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  })
}

/* PERFORMANCE DURATION FORMATTER */
function formatDuration(value: number | undefined): string {
  if (
    typeof value !== 'number' ||
    !Number.isFinite(value) ||
    value < 0
  ) {
    return '—'
  }

  if (value < 1000) {
    return `${Math.round(value)} ms`
  }

  return `${(value / 1000).toFixed(2)} s`
}

/* ORBIT LOGO */
function Orbit() {
  return (
    <svg viewBox="0 0 40 40" aria-label="ORBIT logo">
      <circle
        cx="20"
        cy="20"
        r="13"
        fill="none"
        stroke="#b7aaff"
        strokeWidth="1.5"
      />

      <ellipse
        cx="20"
        cy="20"
        rx="18"
        ry="7"
        transform="rotate(-35 20 20)"
        fill="none"
        stroke="#8c7cff"
        strokeWidth="1.5"
      />

      <circle cx="29" cy="9" r="3" fill="#b7aaff" />
      <circle cx="20" cy="20" r="3" fill="#f1edff" />
    </svg>
  )
}