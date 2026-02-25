export default function LogsTable({ logs }) {
  if (!logs || logs.length === 0) {
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-5 text-center text-slate-500">
        Henüz log yok.
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/50 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-slate-400">
            <th className="text-left p-3">Zaman</th>
            <th className="text-left p-3">Mesaj</th>
            <th className="text-center p-3">Skor</th>
            <th className="text-center p-3">İter.</th>
            <th className="text-center p-3">Onay</th>
            <th className="text-center p-3">Müdahale</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, i) => (
            <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors">
              <td className="p-3 text-slate-500 whitespace-nowrap text-xs">
                {log.timestamp ? new Date(log.timestamp).toLocaleString('tr-TR') : '—'}
              </td>
              <td className="p-3 text-slate-300 max-w-xs">
                <span className="line-clamp-2">{log.employer_message || '—'}</span>
              </td>
              <td className="p-3 text-center">
                {log.overall_score != null ? (
                  <span className={`font-semibold ${log.overall_score >= 4 ? 'text-green-400' : log.overall_score >= 3 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {Number(log.overall_score).toFixed(1)}
                  </span>
                ) : '—'}
              </td>
              <td className="p-3 text-center text-slate-300">{log.iterations ?? '—'}</td>
              <td className="p-3 text-center">
                {log.is_approved === true || log.is_approved === 'True'
                  ? <span className="text-green-400">✅</span>
                  : <span className="text-red-400">❌</span>}
              </td>
              <td className="p-3 text-center">
                {log.intervention_triggered === true || log.intervention_triggered === 'True'
                  ? <span className="text-yellow-400 text-xs">{log.intervention_reason || '⚠️'}</span>
                  : <span className="text-slate-600">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
