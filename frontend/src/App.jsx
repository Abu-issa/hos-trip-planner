import TripForm from './components/TripForm.jsx';

export default function App() {
  return (
    <>
      <header className="topbar">
        <div className="brand"><span className="brand-mark" aria-hidden="true">H</span> HOS Trip Planner</div>
        <span className="topbar-note">TRIP WORKSPACE</span>
      </header>
      <main>
        <div className="intro">
          <p className="eyebrow">PROPERTY CARRIER · 70 HR / 8 DAY</p>
          <h1>HOS Trip Planner</h1>
          <p className="subtitle">Plan property-carrying trips with projected FMCSA Hours of Service stops and daily duty logs.</p>
        </div>
        <TripForm />
        <footer>Property-carrying driver <span aria-hidden="true">·</span> 70-hour / 8-day cycle</footer>
      </main>
    </>
  );
}
