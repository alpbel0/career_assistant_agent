import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip
} from 'recharts'

export default function MetricRadar({ stats }) {
  const data = [
    { metric: 'Truthfulness', score: stats.avg_truthfulness ?? 0 },
    { metric: 'Robustness', score: stats.avg_robustness ?? 0 },
    { metric: 'Helpfulness', score: stats.avg_helpfulness ?? 0 },
    { metric: 'Tone', score: stats.avg_tone ?? 0 },
  ]

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-5">
      <h2 className="text-sm text-slate-400 mb-4">Ortalama EvalOps Metrikleri</h2>
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart data={data}>
          <PolarGrid stroke="#334155" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <PolarRadiusAxis domain={[0, 5]} tick={{ fill: '#64748b', fontSize: 10 }} />
          <Radar
            name="Skor"
            dataKey="score"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.35}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            labelStyle={{ color: '#e2e8f0' }}
            formatter={(v) => [v?.toFixed(2), 'Ort. Skor']}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
