import DutyStatusChart, { dutyRows } from './DutyStatusChart.jsx';
import { reasonLabels } from '../utils/time.js';

function clock(seconds) {
  const total = Math.round(seconds);
  return `${String(Math.floor(total / 3600)).padStart(2, '0')}:${String(Math.floor(total / 60) % 60).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

export default function DailyLogSheet({ log }) {
  return <article className="card daily-log-sheet" aria-labelledby={`daily-log-${log.day}`}>
    <header className="log-heading">
      <div><p className="eyebrow">PROJECTED · RELATIVE DAY</p><h3 id={`daily-log-${log.day}`}>Projected Daily Log — Day {log.day}</h3></div>
      <div className="log-mileage"><span>Total Miles Driven</span><strong>{log.distance_miles.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1})} mi</strong></div>
    </header>
    <DutyStatusChart day={log.day} entries={log.entries} />
    <dl className="log-totals">{dutyRows.map(([status, label]) => <div key={status}><dt>{label}</dt><dd>{clock(log.totals_seconds[status])}</dd></div>)}<div><dt>Total Logged</dt><dd>{clock(Object.values(log.totals_seconds).reduce((sum, value) => sum + value, 0))}</dd></div></dl>
    <p className="log-time-note">Duty totals shown as hours:minutes:seconds, rounded for display. The graph uses exact event times.</p>
    <div className="log-remarks"><h4>Remarks / Duty Changes</h4>
      {log.remarks.length > 0 ? <ul>{log.remarks.map((remark, index) => <li key={index}>
        <time>{clock(remark.second_of_day)}</time><span>{remark.reason === 'POST_TRIP_OFF_DUTY' ? 'Post-trip off duty — projected remainder of day' : reasonLabels[remark.reason] || remark.reason}
          {remark.continued_from_previous_day && ' (continued from previous day)'}
          {remark.location && <small>Estimated route location: {remark.location.latitude.toFixed(4)}, {remark.location.longitude.toFixed(4)}</small>}
        </span>
      </li>)}</ul> : <p>No stationary duty changes on this planning day.</p>}
    </div>
  </article>;
}
