
import {
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
  Copy,
  Columns3,
} from 'lucide-react'

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const API = 'http://127.0.0.1:8000'

type Page = 'Analytics studio' | 'Data sources' | 'SQL explorer'
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
}

interface HistoryItem {
  question: string
}

interface SchemaTable {
  table: string
  columns: string[]
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
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [health, setHealth] = useState<Health>('checking')

  const [schema, setSchema] = useState<SchemaTable[]>([])
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [tab, setTab] = useState<ResultTab>('visual')
  const [sidebar, setSidebar] = useState(true)
  const [activeNav, setActiveNav] = useState<Page>('Analytics studio')
  const [schemaLoading, setSchemaLoading] = useState(false)

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

  const totalRevenue = useMemo(() => {
    if (!result?.rows.length) return null

    const firstRow = result.rows[0]

    for (const key of ['total_revenue', 'total', 'revenue']) {
      const value = firstRow[key]

      if (typeof value === 'number') {
        if (key === 'revenue' && result.rows.length > 1) {
          return result.rows.reduce((sum, row) => {
            const amount = row[key]
            return sum + (typeof amount === 'number' ? amount : 0)
          }, 0)
        }

        return value
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
  }

  const selectNavigation = (page: Page) => {
    setActiveNav(page)
    setError('')

    if (page === 'Analytics studio') {
      newAnalysis()
    }

    if (page === 'Data sources') {
      void refreshSchema()
    }
  }

  return (
    <div className="shell">
      {/* SIDEBAR */}
      <aside className={`sidebar ${!sidebar ? 'collapsed' : ''}`}>
        <div className="brand">
          <div className="mark">
            <Orbit />
          </div>

          {sidebar && (
            <div>
              <b>ORBIT<span>.</span></b>
              <small>INTELLIGENCE WORKSPACE</small>
            </div>
          )}
        </div>

        <div className="workspace">
          <div className="avatar">N</div>

          {sidebar && (
            <>
              <span>
                <b>Northstar Retail</b>
                <small>Free workspace</small>
              </span>
              <ChevronDown size={14} />
            </>
          )}
        </div>

        {sidebar && (
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

            <button className="nav" disabled title="Coming soon">
              <Layers3 />
              Agent workflows
              <small>SOON</small>
            </button>

            <div className="side-rule" />

            <label>RECENT ANALYSES</label>

            {history.slice(0, 5).map((item, index) => (
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

            {history.length === 0 && (
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
            {sidebar && (
              <span>
                <b>Demo environment</b>
                <small>Local synthetic dataset</small>
              </span>
            )}
          </div>

          <div className="profile">
            <div className="avatar">NK</div>
            {sidebar && (
              <span>
                <b>Analyst workspace</b>
                <small>Personal account</small>
              </span>
            )}
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main>
        <header>
          <div className="crumb">
            <button
              onClick={() => setSidebar((previous) => !previous)}
              title="Toggle sidebar"
            >
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
            <div className="avatar">NK</div>
          </div>
        </header>

        <div className="content">
          {activeNav === 'Data sources' ? (
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
              {/* DASHBOARD HEADING */}
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

              {/* ASK ORBIT */}
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

              {/* KPI METRICS */}
              <div className="metrics">
                <Metric
                  icon={<TrendingUp />}
                  label="TOTAL REVENUE"
                  value={totalRevenue !== null ? money(totalRevenue) : '—'}
                  note="Revenue in current result"
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

              {/* RESULTS HEADER */}
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
                  {/* RESULT CARD */}
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

                    {/* RESULT TABS */}
                    <div className="tabs">
                      <button
                        className={tab === 'visual' ? 'chosen' : ''}
                        onClick={() => setTab('visual')}
                      >
                        <BarChart3 />
                        Visualization
                      </button>

                      <button
                        className={tab === 'table' ? 'chosen' : ''}
                        onClick={() => setTab('table')}
                      >
                        <Table2 />
                        Data table
                      </button>

                      <button
                        className={tab === 'sql' ? 'chosen' : ''}
                        onClick={() => setTab('sql')}
                      >
                        <Terminal />
                        SQL query
                      </button>
                    </div>

                    <div className="tabbody">
                      {/* AUTOMATIC KPI OR CHART */}
                      {tab === 'visual' && (
                        isSingleValue ? (
                          <div className="single-kpi">
                            <span>KEY BUSINESS METRIC</span>

                            <h2>
                              {totalRevenue !== null
                                ? money(totalRevenue)
                                : formatValue(
                                    Object.values(result.rows[0] ?? {})[0],
                                  )}
                            </h2>

                            <p>{result.answer}</p>

                            <small>
                              Single-value result · No chart required
                            </small>
                          </div>
                        ) : result.chart && result.chart.data.length > 0 ? (
                          <>
                            <div className="chart-title">
                              {result.chart.label} by {result.chart.xKey}
                              <small>QUERY OUTPUT</small>
                            </div>

                            <ResponsiveContainer width="100%" height={300}>
                              <BarChart
                                data={result.chart.data}
                                margin={{
                                  top: 10,
                                  right: 10,
                                  left: 0,
                                  bottom: 5,
                                }}
                              >
                                <CartesianGrid
                                  stroke="#253146"
                                  strokeDasharray="3 3"
                                  vertical={false}
                                />

                                <XAxis
                                  dataKey={result.chart.xKey}
                                  tick={{
                                    fill: '#a5b2c9',
                                    fontSize: 11,
                                  }}
                                  axisLine={false}
                                  tickLine={false}
                                />

                                <YAxis
                                  tick={{
                                    fill: '#a5b2c9',
                                    fontSize: 11,
                                  }}
                                  axisLine={false}
                                  tickLine={false}
                                />

                                <Tooltip
                                  contentStyle={{
                                    background: '#101827',
                                    border: '1px solid #51447e',
                                    borderRadius: 10,
                                    color: '#e8edf7',
                                  }}
                                />

                                <Bar
                                  dataKey={result.chart.yKey}
                                  fill="#9b8aff"
                                  radius={[6, 6, 0, 0]}
                                  maxBarSize={58}
                                />
                              </BarChart>
                            </ResponsiveContainer>
                          </>
                        ) : (
                          <div className="single-kpi">
                            <span>ANALYSIS RESULT</span>
                            <h2>{result.row_count} records</h2>
                            <p>{result.answer}</p>
                            <small>
                              No visualization available for this result
                            </small>
                          </div>
                        )
                      )}

                      {/* DATA TABLE */}
                      {tab === 'table' && <DataTable result={result} />}

                      {/* SQL */}
                      {tab === 'sql' && (
                        <div className="sql">
                          <div>
                            <span>● SQL VALIDATED</span>

                            <button onClick={() => void copySQL()}>
                              <Copy />
                              Copy SQL
                            </button>
                          </div>

                          <pre>{result.sql}</pre>

                          <small>
                            <ShieldCheck />
                            Single SELECT · approved schema · read-only connection
                          </small>
                        </div>
                      )}
                    </div>
                  </section>

                  {/* RIGHT SIDE */}
                  <div className="stack">
                    <section className="panel">
                      <div className="panel-head">
                        <b>AGENT TRACE</b>
                        <span className="done">● COMPLETE</span>
                      </div>

                      <div className="trace">
                        {result.steps.map((step, index) => (
                          <div
                            className="step"
                            key={`${step.name}-${index}`}
                          >
                            <i><Check /></i>

                            <div>
                              <b>{step.name}</b>
                              <small>{step.detail}</small>
                            </div>

                            {index !== result.steps.length - 1 && <u />}
                          </div>
                        ))}
                      </div>
                    </section>

                    <section className="panel catalog">
                      <button
                        onClick={() => selectNavigation('Data sources')}
                      >
                        <b><Database /> DATA CATALOG</b>
                        <ArrowUpRight />
                      </button>

                      <p>Connected demo warehouse</p>

                      <small className="dbstatus">
                        ● SQLite · {schema.length} tables
                      </small>
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
    (sum, table) => sum + (Array.isArray(table.columns) ? table.columns.length : 0),
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
          {health === 'online' ? 'CONNECTED' : health === 'offline' ? 'OFFLINE' : 'CHECKING'}
          <small>LOCAL SQLITE DEMO WAREHOUSE</small>
        </div>
      </div>

      <div className="metrics">
        <Metric
          icon={<Database />}
          label="CONNECTION"
          value={health === 'online' ? 'Online' : health === 'offline' ? 'Offline' : 'Checking'}
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
                className={`source-table-item ${selectedTable === table.table ? 'selected' : ''}`}
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
              <th key={column}>
                {column.replace(/_/g, ' ')}
              </th>
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

  return String(value)
}

function money(value: number): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  })
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
