import { useEffect, useMemo } from 'react';
import { Icon, divIcon, latLngBounds } from 'leaflet';
import { duration, tripTime, reasonLabels } from '../utils/time.js';
import { MapContainer, Marker, Popup, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet';
import markerUrl from 'leaflet/dist/images/marker-icon.png';
import markerRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';
import 'leaflet/dist/leaflet.css';

const markers = [
  ['current', 'Current Location', '1'],
  ['pickup', 'Pickup', '2'],
  ['dropoff', 'Dropoff', '3'],
].map(([key, label, number]) => ({
  key, label, number,
  icon: new Icon({
    iconUrl: markerUrl, iconRetinaUrl: markerRetinaUrl, shadowUrl: markerShadowUrl,
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
    shadowSize: [41, 41], className: `marker-${key}`,
  }),
}));

function FitRoute({ positions }) {
  const map = useMap();
  useEffect(() => {
    const fit = () => {
      map.invalidateSize();
      map.fitBounds(latLngBounds(positions), { padding: [38, 38], maxZoom: 13, animate: false });
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map, positions]);
  return null;
}

export default function RouteMap({ route, locations, stops = [] }) {
  const lines = useMemo(() => route.legs.map((leg) => (
    leg.geometry.coordinates.map(([longitude, latitude]) => [latitude, longitude])
  )), [route]);
  const positions = useMemo(() => [
    ...lines.flat(), ...Object.values(locations).map((location) => [location.latitude, location.longitude]),
  ], [lines, locations]);
  const locationMarkers = useMemo(() => markers.map(marker => {
    const point = locations[marker.key];
    const coincident = markers.filter(other => locations[other.key].latitude === point.latitude
      && locations[other.key].longitude === point.longitude);
    const offset = (coincident.findIndex(other => other.key === marker.key) - (coincident.length - 1) / 2) * 30;
    // Separate coincident icons in screen pixels without changing route coordinates.
    return { ...marker, offset, icon: new Icon({ ...marker.icon.options,
      iconAnchor: [12 - offset, 41], popupAnchor: [1 + offset, -34],
    }) };
  }), [locations]);

  return (
    <section className="card route-card" aria-labelledby="route-title">
      <div className="card-heading"><h2 id="route-title">Your road route</h2><p>Current location → Pickup → Dropoff</p></div>
      <MapContainer className="route-map" center={positions[0]} zoom={5} scrollWheelZoom={false}>
        <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
        {route.legs.map((leg, index) => <Polyline key={leg.id} positions={lines[index]} pathOptions={{ color: index === 0 ? '#1b5b60' : '#b55f22', weight: 5, opacity: 0.85 }} />)}
        {locationMarkers.map(({ key, label, number, icon, offset }) => <Marker key={key} position={[locations[key].latitude, locations[key].longitude]} icon={icon} title={label} alt={label}>
          <Tooltip direction="top" offset={[offset, -40]}>{number}. {label}</Tooltip>
          <Popup><strong>{number}. {label}</strong><br />{locations[key].display_name}
            {stops.filter(s => s.kinds.includes(key.toUpperCase())).map(s => <p key={s.id}>{s.kinds.map(k => reasonLabels[k]).join(' + ')}<br />{tripTime(s.start_offset_seconds)} · {duration(s.duration_seconds)}</p>)}
          </Popup>
        </Marker>)}
        {stops.filter(s => !s.kinds.includes('PICKUP') && !s.kinds.includes('DROPOFF')).map(stop => {
          const kind = stop.kinds.includes('DAILY_REST') ? 'rest' : stop.kinds.includes('FUEL') ? 'fuel' : 'break';
          const title = stop.kinds.map(k => reasonLabels[k]).join(' + ');
          return <Marker key={stop.id} position={[stop.location.latitude, stop.location.longitude]} title={title}
            icon={divIcon({className: `hos-marker hos-${kind}`, html: kind === 'rest' ? 'R' : kind === 'fuel' ? 'F' : 'B', iconSize: [26, 26], iconAnchor: [13, 13]})}>
            <Popup><strong>{title}</strong><br />{tripTime(stop.start_offset_seconds)}<br />{duration(stop.duration_seconds)}<br />Estimated route location: {stop.location.latitude.toFixed(4)}, {stop.location.longitude.toFixed(4)}<br />Facility not verified.</Popup>
          </Marker>;
        })}
        <FitRoute positions={positions} />
      </MapContainer>
      <div className="route-details">
        <div className="route-legend"><span><i className="leg-one" />Current → Pickup</span><span><i className="leg-two" />Pickup → Dropoff</span></div>
        <div className="marker-legend" aria-label="Map marker legend"><span>1 · Current</span><span>2 · Pickup</span><span>3 · Dropoff</span>{stops.length > 0 && <><span><b className="hos-fuel">F</b> Fuel</span><span><b className="hos-break">B</b> 30-minute break</span><span><b className="hos-rest">R</b> 10-hour rest</span></>}</div>
        <ol className="resolved-locations">{markers.map(({ key, label }) => <li key={key}><strong>{label}</strong><span>{locations[key].display_name}</span></li>)}</ol>
        <p className="hint">Geocoding and map data © OpenStreetMap contributors. Routing by OSRM. Locations may snap to nearby roads.</p>
      </div>
    </section>
  );
}
