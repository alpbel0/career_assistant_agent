export default function StatCard({ title, value, subtitle, color }) {
  const colorMap = {
    blue: 'border-blue-500 bg-blue-500/10',
    green: 'border-green-500 bg-green-500/10',
    yellow: 'border-yellow-500 bg-yellow-500/10',
    red: 'border-red-500 bg-red-500/10',
    purple: 'border-purple-500 bg-purple-500/10',
  }

  const textMap = {
    blue: 'text-blue-400',
    green: 'text-green-400',
    yellow: 'text-yellow-400',
    red: 'text-red-400',
    purple: 'text-purple-400',
  }

  return (
    <div className={`rounded-xl border ${colorMap[color] || colorMap.blue} p-5`}>
      <p className="text-sm text-slate-400 mb-1">{title}</p>
      <p className={`text-3xl font-bold ${textMap[color] || textMap.blue}`}>{value}</p>
      {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
    </div>
  )
}
