import { duration } from '../utils/time.js';

export default function TripSummary({ summary, hos }) {
  const compliant = hos.status === 'COMPLIANT_PLAN';
  const cards = [
    ['Total Distance', `${Math.round(summary.distance_miles).toLocaleString()} mi`],
    ['Pure Driving Time', duration(summary.estimated_driving_seconds)],
    ['Cycle Used at Start', `${summary.current_cycle_used} / 70 hr`],
    ...(compliant ? [
      ['Projected Trip Duration', duration(summary.planned_elapsed_seconds)],
      ['Projected Cycle Used', `${summary.projected_cycle_used.toFixed(2)} / 70 hr`],
      ['10-Hour Rests', summary.daily_rest_count],
      ['Fuel Stops', summary.fuel_stop_count],
      ['Daily Logs', summary.daily_log_count],
    ] : [
      ['Cycle Hours Available at Start', `${summary.cycle_hours_available_at_start} hr`],
      ['On-Duty Work Required', duration(summary.cycle_work_required_seconds)],
      ['Cycle Usage Needed to Finish', `${summary.required_cycle_used_if_completed.toFixed(2)} / 70 hr`],
    ]),
  ];
  return (
    <section className="trip-summary" aria-label="Trip summary">
      {cards.map(([label, value]) => <div className="summary-card" key={label}><h3>{label}</h3><p>{value}</p></div>)}
    </section>
  );
}
