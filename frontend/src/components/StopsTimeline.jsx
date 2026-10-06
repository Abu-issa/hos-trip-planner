import { duration, tripTime, reasonLabels, statusLabels } from '../utils/time.js';

export default function StopsTimeline({ events }) {
  return <section className="card timeline-card" aria-labelledby="timeline-title">
    <div className="card-heading"><h2 id="timeline-title">Projected duty timeline</h2><p>Times are relative to trip start. Day 1 · 00:00 means departure, not local midnight.</p></div>
    <ol className="duty-timeline">{events.map(event => <li key={event.id} className={`duty-${event.status.toLowerCase()}`}>
      <div className="event-time">{tripTime(event.start_offset_seconds)}<span>to {tripTime(event.end_offset_seconds)}</span></div>
      <div className="event-body"><h3>{reasonLabels[event.reason]} <span>{duration(event.duration_seconds)}</span></h3>
        <p>{statusLabels[event.status]}{event.status === 'DRIVING' ? ` · ${event.distance_miles.toLocaleString(undefined, {maximumFractionDigits: 1})} mi` : ''}</p>
        {event.status !== 'DRIVING' && <p className="hint">Estimated route point: {event.start_location.latitude.toFixed(4)}, {event.start_location.longitude.toFixed(4)}</p>}
      </div>
    </li>)}</ol>
  </section>;
}
