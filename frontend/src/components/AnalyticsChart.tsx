
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

interface ChartData {
  type: string
  xKey: string
  yKey: string
  label: string
  data: Record<string, string | number>[]
}

interface AnalyticsChartProps {
  chart: ChartData
}

export default function AnalyticsChart({
  chart,
}: AnalyticsChartProps) {
  return (
    <div className="chart-wrap">
      <div className="chart-title">
        <b>{chart.label || 'Analysis overview'}</b>
        <small>{chart.data.length} DATA POINTS</small>
      </div>

      <ResponsiveContainer width="100%" height={290}>
        <BarChart
          data={chart.data}
          margin={{
            top: 12,
            right: 12,
            left: 0,
            bottom: 8,
          }}
        >
          <CartesianGrid
            stroke="#29364d"
            strokeDasharray="3 3"
            vertical={false}
          />

          <XAxis
            dataKey={chart.xKey}
            tick={{
              fill: '#8794aa',
              fontSize: 10,
            }}
            axisLine={{
              stroke: '#34415a',
            }}
            tickLine={false}
          />

          <YAxis
            tick={{
              fill: '#8794aa',
              fontSize: 10,
            }}
            axisLine={false}
            tickLine={false}
            width={58}
          />

          <Tooltip
            contentStyle={{
              background: '#111b2b',
              border: '1px solid #46516b',
              borderRadius: 9,
              color: '#edf1fb',
              fontSize: 11,
            }}
          />

          <Bar
            dataKey={chart.yKey}
            name={chart.label}
            fill="#9b8cff"
            radius={[5, 5, 0, 0]}
            maxBarSize={48}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
