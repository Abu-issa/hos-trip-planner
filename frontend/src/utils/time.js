export function duration(seconds) {
  if (seconds == null) return 'Unavailable';
  const minutes = Math.round(seconds / 60);
  const hours = Math.floor(minutes / 60);
  return hours === 0 ? `${minutes} min` : `${hours} hr${minutes % 60 ? ` ${minutes % 60} min` : ''}`;
}

export function tripTime(seconds) {
  const minutes = Math.floor((seconds + 0.001) / 60);
  return `Day ${Math.floor(minutes / 1440) + 1} · ${String(Math.floor(minutes / 60) % 24).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

export const reasonLabels = {
  TRAVEL: 'Driving', PICKUP: 'Pickup', DROPOFF: 'Dropoff', FUEL: 'Fuel Stop',
  REQUIRED_BREAK: 'Required 30-Minute Break', DAILY_REST: '10-Hour Sleeper Rest',
};

export const statusLabels = {OFF_DUTY: 'Off Duty', SLEEPER_BERTH: 'Sleeper Berth', DRIVING: 'Driving', ON_DUTY_NOT_DRIVING: 'On Duty (Not Driving)'};
