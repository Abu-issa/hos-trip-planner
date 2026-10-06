import { useEffect, useRef, useState } from 'react';
import { planTrip } from '../services/api.js';
import TripSummary from './TripSummary.jsx';
import RouteMap from './RouteMap.jsx';
import StopsTimeline from './StopsTimeline.jsx';
import DailyLogsSection from './DailyLogsSection.jsx';

const initialValues = {
  current_location: '', pickup_location: '', dropoff_location: '', current_cycle_used: '',
};
const locations = [
  ['current_location', 'Current Location', 'e.g. Chicago, IL'],
  ['pickup_location', 'Pickup Location', 'e.g. Indianapolis, IN'],
  ['dropoff_location', 'Dropoff Location', 'e.g. Dallas, TX'],
];

export default function TripForm() {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const overviewRef = useRef(null);
  useEffect(() => {
    if (result) overviewRef.current?.focus({ preventScroll: false });
  }, [result]);

  function change(event) {
    const { name, value } = event.target;
    setValues((previous) => ({ ...previous, [name]: value }));
    setErrors((previous) => ({ ...previous, [name]: undefined }));
    setMessage('');
    setResult(null);
  }

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    setResult(null);
    setMessage('');
    const validation = {};
    const input = { ...values, current_cycle_used: Number(values.current_cycle_used) };
    for (const [name] of locations) {
      input[name] = values[name].trim();
      if (!input[name]) validation[name] = 'Enter a location.';
    }
    if (values.current_cycle_used.trim() === '' || !Number.isFinite(input.current_cycle_used)
      || input.current_cycle_used < 0 || input.current_cycle_used > 70) {
      validation.current_cycle_used = 'Enter a number from 0 to 70.';
    }
    setErrors(validation);
    if (Object.keys(validation).length) return;
    setLoading(true);
    try {
      setResult(await planTrip(input));
    } catch (error) {
      const providerError = error.response?.data?.error;
      if (error.response?.status === 400 || providerError) {
        const fieldErrors = {};
        for (const [key, value] of Object.entries(providerError?.fields || error.response.data || {})) {
          if (key in initialValues) fieldErrors[key] = Array.isArray(value) ? value.join(' ') : String(value);
        }
        setErrors(fieldErrors);
        const friendly = {
          LOCATION_NOT_FOUND: "We couldn't find that location. Try entering a city and state or a more specific address.",
          PROVIDER_TIMEOUT: 'The mapping service took too long to respond. Please try again.',
          PROVIDER_UNAVAILABLE: 'The mapping service is temporarily unavailable. Please try again shortly.',
          INVALID_PROVIDER_RESPONSE: 'The mapping service could not return a usable route. Please try again shortly.',
          NO_ROUTE_FOUND: 'No drivable route could be found for the selected locations.',
        };
        setMessage(friendly[providerError?.code] || (Object.keys(fieldErrors).length ? 'Please check the highlighted fields.' : 'The request could not be validated. Please try again.'));
      } else {
        setMessage(error.response
          ? 'The server could not process your request. Please try again.'
          : 'Unable to reach the server. Check your connection and try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
    <section className="card" aria-labelledby="form-title">
      <div className="card-heading"><h2 id="form-title">Trip details</h2><p>Enter your locations and the hours already used in your current cycle.</p></div>
      <form onSubmit={submit} aria-busy={loading}>
        <fieldset disabled={loading}>
          <legend className="sr-only">Trip locations and cycle hours</legend>
          <div className="fields">
            {locations.map(([name, label, placeholder], index) => (
              <div className="field" key={name}>
                <label htmlFor={name}><span className="step" aria-hidden="true">{index + 1}</span>{label}</label>
                <input id={name} name={name} value={values[name]} onChange={change} placeholder={placeholder}
                  required maxLength={255} aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? `${name}-error` : undefined} />
                {errors[name] && <p className="field-error" id={`${name}-error`} role="alert">{errors[name]}</p>}
              </div>
            ))}
            <div className="field cycle-field">
              <label htmlFor="current_cycle_used">Current Cycle Used (Hours)</label>
              <input id="current_cycle_used" name="current_cycle_used" type="number" min="0" max="70" step="any" required
                value={values.current_cycle_used} onChange={change} placeholder="e.g. 15" aria-invalid={Boolean(errors.current_cycle_used)}
                aria-describedby={`cycle-hint${errors.current_cycle_used ? ' current_cycle_used-error' : ''}`} />
              <p className="hint" id="cycle-hint">Hours already used out of your 70-hour cycle.</p>
              {errors.current_cycle_used && <p className="field-error" id="current_cycle_used-error" role="alert">{errors.current_cycle_used}</p>}
            </div>
          </div>
        </fieldset>
        {message && <p className="error-banner" role="alert">{message}</p>}
        {loading && <div className="loading-panel" role="status"><span className="spinner" aria-hidden="true" /><div><strong>Planning your trip…</strong><p>Resolving locations and calculating the route. This may take a moment.</p></div></div>}
        <div className="form-actions"><span>All four fields are required.</span><button type="submit" disabled={loading}>{loading ? 'Planning Route...' : 'Plan Trip'}<span aria-hidden="true"> →</span></button></div>
      </form>
    </section>
    {!result && !loading && !message && <aside className="empty-state"><strong>Your trip, from route to daily logs</strong><p>Enter the three locations and current cycle usage to see the road route, projected stops and rests, and daily duty logs.</p></aside>}
    {result && <div className="results">
      <h2 className="overview-heading" ref={overviewRef} tabIndex={-1}>Trip overview</h2>
      {result.hos.status === 'COMPLIANT_PLAN'
        ? <p className="result-status" role="status">Projected schedule ready · Compliant under the stated assumptions</p>
        : <div className="cycle-warning" role="alert"><h2>Insufficient Cycle Hours</h2><p>This trip requires approximately {(result.summary.cycle_work_required_seconds / 3600).toFixed(2)} on-duty hours, but only {result.summary.cycle_hours_available_at_start} hours are available in the supplied 70-hour cycle.</p><p>No complete HOS schedule or daily logs were generated. The road route remains available for reference.</p></div>}
      <TripSummary summary={result.summary} hos={result.hos} />
      <p className="planning-note">Pure driving time is the routing provider's estimate. Planned duration includes pickup, dropoff, fuel, breaks, and rests. This route is not verified for truck restrictions; estimated stop points are not confirmed fuel or parking facilities.</p>
      <RouteMap route={result.route} locations={result.locations} stops={result.stops} />
      {result.duty_events.length > 0 && <StopsTimeline events={result.duty_events} />}
      <DailyLogsSection logs={result.daily_logs} hos={result.hos} />
      <details className="assumptions bottom-assumptions"><summary>Planning Assumptions</summary><ul>
        <li>Property-carrying driver on a 70-hour / 8-day cycle; no adverse-condition exception.</li>
        <li>Fresh 11-hour driving and 14-hour window clocks after at least 10 hours off duty. Supplied cycle usage remains consumed.</li>
        <li>Pickup and dropoff: 1 hour each. Fuel: 30 minutes, at least every 1,000 miles, starting full.</li>
        <li>No historical recapture or automatic 34-hour restart is assumed.</li>
        <li>General road routing does not verify commercial-truck restrictions. Generated stops are estimated coordinates, not verified truck facilities.</li>
        <li>Days are relative to departure. Final-day post-trip off duty is a projection for completing the daily log.</li>
      </ul></details>
    </div>}
    </>
  );
}
