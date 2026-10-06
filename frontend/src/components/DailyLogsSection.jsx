import DailyLogSheet from './DailyLogSheet.jsx';

export default function DailyLogsSection({ logs, hos }) {
  return <section className="daily-logs-section" aria-labelledby="daily-logs-title">
    <div className="daily-logs-intro"><p className="eyebrow">DUTY RECORD PROJECTION</p><h2 id="daily-logs-title">Projected daily logs</h2>
      <p>Projected logs are planning outputs based on estimated route times and the supplied cycle usage. They are not certified ELD records.</p>
      {hos.status === 'INSUFFICIENT_CYCLE_HOURS'
        ? <p className="logs-unavailable">Daily logs cannot be generated because the trip cannot be completed with the supplied cycle hours.</p>
        : <><p>{logs.length} planning {logs.length === 1 ? 'day' : 'days'} · Trip starts on Day 1 at 00:00. Each sheet covers 24 hours, without a calendar date or timezone.</p><p>After dropoff, the remainder of the final day is projected Off Duty to complete the log. This does not change trip duration or cycle usage.</p></>}
    </div>
    {logs.map(log => <DailyLogSheet key={log.day} log={log} />)}
  </section>;
}
