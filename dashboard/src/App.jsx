import { useState, useEffect, useCallback } from 'react'
import StatCard from './components/StatCard'
import MetricRadar from './components/MetricRadar'
import LogsTable from './components/LogsTable'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

export default function App() {
  const [stats, setStats] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/stats`),
        fetch(`${API_BASE}/logs?limit=50`)
      ])
      if (!statsRes.ok || !logsRes.ok) throw new Error('API hatası')
      const statsData = await statsRes.json()
      const logsData = await logsRes.json()
      setStats(statsData)
      setLogs(logsData.logs || [])
      setLastUpdated(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Career Assistant</h1>
            <p className="text-xs text-slate-500">EvalOps Dashboard</p>
          </div>
          <div className="flex items-center gap-4">
            {lastUpdated && (
              <span className="text-xs text-slate-500">
                {lastUpdated.toLocaleTimeString('tr-TR')}
              </span>
            )}
            <button
              onClick={fetchData}
              disabled={loading}
              className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Yükleniyor...' : '↻ Yenile'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">

        {error && (
          <div className="rounded-xl border border-red-500/50 bg-red-500/10 p-4 text-red-400 text-sm">
            ⚠️ API'ye bağlanılamadı: {error}
            <span className="text-red-500 ml-2">— Bot çalışıyor mu?</span>
          </div>
        )}

        {/* Stat Cards */}
        <section>
          <h2 className="text-xs uppercase tracking-widest text-slate-500 mb-4">Genel Özet</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <StatCard
              title="Toplam Mesaj"
              value={stats?.total_interactions ?? '—'}
              subtitle="İşlenen konuşma"
              color="blue"
            />
            <StatCard
              title="Onay Oranı"
              value={stats?.approval_rate != null ? `%${(stats.approval_rate * 100).toFixed(0)}` : '—'}
              subtitle="Judge onayladı"
              color="green"
            />
            <StatCard
              title="Ort. Skor"
              value={stats?.avg_overall_score != null ? Number(stats.avg_overall_score).toFixed(2) : '—'}
              subtitle="Overall (1-5)"
              color="purple"
            />
            <StatCard
              title="Ort. İterasyon"
              value={stats?.avg_iterations != null ? Number(stats.avg_iterations).toFixed(1) : '—'}
              subtitle="Revizyon turu"
              color="yellow"
            />
            <StatCard
              title="Müdahale"
              value={stats?.intervention_count ?? '—'}
              subtitle="Admin'e yönlenen"
              color="red"
            />
          </div>
        </section>

        {/* Radar + Extra Stats */}
        <section className="grid md:grid-cols-2 gap-6">
          {stats && <MetricRadar stats={stats} />}

          <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-5 space-y-4">
            <h2 className="text-sm text-slate-400">Metrik Detayları</h2>
            {[
              { label: 'Truthfulness', key: 'avg_truthfulness', color: 'bg-blue-500' },
              { label: 'Robustness', key: 'avg_robustness', color: 'bg-green-500' },
              { label: 'Helpfulness', key: 'avg_helpfulness', color: 'bg-purple-500' },
              { label: 'Tone', key: 'avg_tone', color: 'bg-yellow-500' },
            ].map(({ label, key, color }) => {
              const val = stats?.[key] ?? 0
              const pct = (val / 5) * 100
              return (
                <div key={key}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">{label}</span>
                    <span className="text-slate-300 font-medium">{val ? Number(val).toFixed(2) : '—'} / 5</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${color} rounded-full transition-all duration-500`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}

            <div className="pt-2 border-t border-slate-700 grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="text-slate-500">İlk denemede onay</p>
                <p className="text-white font-semibold">{stats?.first_attempt_approval_rate != null ? `%${(stats.first_attempt_approval_rate * 100).toFixed(0)}` : `%${stats?.approval_rate != null ? (stats.approval_rate * 100).toFixed(0) : '—'}`}</p>
              </div>
              <div>
                <p className="text-slate-500">Kategori dağılımı</p>
                <p className="text-white font-semibold text-xs">
                  {stats?.category_counts
                    ? Object.entries(stats.category_counts)
                        .filter(([, v]) => v > 0)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(', ') || '—'
                    : '—'}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Logs Table */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs uppercase tracking-widest text-slate-500">Son İnteraksiyonlar</h2>
            <span className="text-xs text-slate-600">{logs.length} kayıt</span>
          </div>
          <LogsTable logs={[...logs].reverse()} />
        </section>

        {/* Footer */}
        <footer className="text-center text-xs text-slate-600 py-4">
          Career Assistant AI Agent — Yiğitalp BEL
        </footer>
      </main>
    </div>
  )
}
