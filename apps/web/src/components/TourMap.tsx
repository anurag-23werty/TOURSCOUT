import L from "leaflet";
import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import { LABEL_TEXT } from "../format";
import type { Label, MetroRow, Stop } from "../types";

const LABEL_COLOR: Record<Label, string> = {
  unserved: "#e6457a",
  proven: "#22306e",
  potential: "#8c94b8",
  low: "#c3c9da",
};

interface Props {
  metros: MetroRow[];
  stops: Stop[];
  active: number | null;
  onSelect: (index: number) => void;
}

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  const key = points.map((p) => p.join(",")).join("|");
  useEffect(() => {
    map.invalidateSize(); // the container may have been resized (mobile layout) since the map mounted
    // Less padding on a phone: 40 px each side pushed a Midwest route down a whole zoom level at 390 px wide.
    const pad = map.getSize().x < 500 ? 20 : 40; // ≥ 20 so the 26 px stop pins at the edges aren't cut off
    if (points.length === 1) map.setView(points[0], 8);
    else if (points.length > 1) map.fitBounds(L.latLngBounds(points), { padding: [pad, pad], maxZoom: 9 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map]);
  return null;
}

export function TourMap({ metros, stops, active, onSelect }: Props) {
  const routed = stops.filter((s) => s.lat != null && s.lon != null);
  const route = routed.map((s) => [s.lat!, s.lon!] as [number, number]);
  const focus = route.length ? route : metros.slice(0, 12).map((m) => [m.lat, m.lon] as [number, number]);
  const pins = useMemo(
    () => routed.map((_, i) => L.divIcon({ className: "", html: `<span class="stop-pin${i === active ? " is-active" : ""}">${i + 1}</span>`, iconSize: [26, 26] })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [routed.length, active],
  );

  return (
    <MapContainer
      center={[39.5, -92]}
      zoom={4}
      zoomSnap={0.25}
      scrollWheelZoom
      className="h-full w-full"
      aria-label="Map of demand and the tour route"
    >
      {/* Esri's light-gray canvas needs no API key (CARTO's basemaps started requiring one). */}
      <TileLayer
        attribution="Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors"
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        maxZoom={16}
      />
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
        maxZoom={16}
        opacity={0.8}
      />
      {metros.map((m) => (
        <CircleMarker
          key={m.metro}
          center={[m.lat, m.lon]}
          radius={4 + (m.demand / 100) * 14}
          pathOptions={{ color: LABEL_COLOR[m.label], fillColor: LABEL_COLOR[m.label], fillOpacity: 0.28, weight: 1.5 }}
        >
          <Tooltip>
            <strong>{m.metro}</strong>
            <br />
            {LABEL_TEXT[m.label]}: demand {Math.round(m.demand)}, reach {Math.round(m.reach)}
          </Tooltip>
        </CircleMarker>
      ))}
      {route.length > 1 && <Polyline positions={route} pathOptions={{ color: "#22306e", weight: 3, dashArray: "6 8" }} />}
      {routed.map((s, i) => (
        <Marker key={`${s.metro}-${s.date}`} position={[s.lat!, s.lon!]} icon={pins[i]} eventHandlers={{ click: () => onSelect(i) }} keyboard>
          <Tooltip direction="top" offset={[0, -12]}>
            {s.date}: {s.metro}
          </Tooltip>
        </Marker>
      ))}
      <FitBounds points={focus} />
    </MapContainer>
  );
}
