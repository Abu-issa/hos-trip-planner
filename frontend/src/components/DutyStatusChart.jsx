import { useId } from 'react';

export const dutyRows = [
  ['OFF_DUTY', 'Off Duty'],
  ['SLEEPER_BERTH', 'Sleeper Berth'],
  ['DRIVING', 'Driving'],
  ['ON_DUTY_NOT_DRIVING', 'On Duty (Not Driving)'],
];

export default function DutyStatusChart({ entries, day }) {
  const titleId = useId();
  const left = 164;
  const width = 864;
  const top = 48;
  const rowHeight = 48;
  const x = seconds => left + seconds / 86400 * width;
  const y = status => top + dutyRows.findIndex(([key]) => key === status) * rowHeight + rowHeight / 2;
  // One path: horizontal segments and vertical transitions at unrounded timestamps.
  const trace = entries.map((entry, index) => (
    `${index === 0 ? `M ${x(entry.start_second_of_day)} ${y(entry.status)}` : `V ${y(entry.status)}`} H ${x(entry.end_second_of_day)}`
  )).join(' ');

  return <div className="duty-chart-scroll" tabIndex={0} role="region" aria-label={`Day ${day} duty graph; scroll horizontally on small screens`}>
    <svg className="duty-chart" viewBox="0 0 1052 270" role="img" aria-labelledby={titleId}>
      <title id={titleId}>Day {day}: projected duty status from 00:00 to 24:00. Four rows: Off Duty, Sleeper Berth, Driving, and On Duty (Not Driving).</title>
      <text x={left} y="16" className="chart-caption">MIDNIGHT</text>
      <text x={x(43200)} y="16" textAnchor="middle" className="chart-caption">NOON</text>
      {dutyRows.map(([status, label], index) => <g key={status}>
        <rect x={left} y={top + index * rowHeight} width={width} height={rowHeight} fill={index % 2 === 0 ? '#f5f7f8' : '#fff'} />
        <text x={left - 12} y={y(status) + 4} textAnchor="end" className="chart-row-label">{label}</text>
      </g>)}
      {Array.from({length: 97}, (_, tick) => <line key={tick} x1={left + tick * width / 96} x2={left + tick * width / 96} y1={top} y2={top + 4 * rowHeight} className={tick % 4 === 0 ? 'chart-hour-line' : 'chart-quarter-line'} />)}
      {Array.from({length: 25}, (_, hour) => <text key={hour} x={left + hour * width / 24} y="36" textAnchor="middle" className="chart-hour-label">{hour}</text>)}
      {Array.from({length: 5}, (_, row) => <line key={row} x1={left} x2={left + width} y1={top + row * rowHeight} y2={top + row * rowHeight} className="chart-row-line" />)}
      <path className="duty-trace" d={trace} fill="none" stroke="#15545a" strokeWidth="3" strokeLinejoin="round" />
      <text x={left} y="261" className="chart-caption">24-HOUR PLANNING DAY · QUARTER-HOUR GRID</text>
    </svg>
  </div>;
}
