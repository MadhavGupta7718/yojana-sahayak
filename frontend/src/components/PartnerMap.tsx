"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type Partner = {
  id: number;
  name: string;
  latitude?: number | null;
  longitude?: number | null;
  distance_km?: number | null;
  address?: string | null;
  state?: string | null;
  district?: string | null;
  source_url?: string | null;
};

export default function PartnerMap({
  userLat,
  userLon,
  partners,
  radiusKm,
}: {
  userLat: number;
  userLon: number;
  partners: Partner[];
  radiusKm?: number | null;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;

    const map = L.map(ref.current).setView([userLat, userLon], radiusKm && radiusKm <= 40 ? 10 : 8);
    mapRef.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    const icon = L.icon({
      iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
      iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
      shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      popupAnchor: [1, -34],
      shadowSize: [41, 41],
    });

    L.marker([userLat, userLon], { icon })
      .addTo(map)
      .bindPopup("<strong>Your search location</strong>");

    if (radiusKm) {
      L.circle([userLat, userLon], {
        radius: radiusKm * 1000,
        color: "#0b3a5b",
        fillOpacity: 0.08,
      }).addTo(map);
    }

    const withCoords = partners.filter((p) => p.latitude != null && p.longitude != null);
    withCoords.forEach((p) => {
      const html = [
        `<strong>${p.name}</strong>`,
        [p.district, p.state].filter(Boolean).join(", "),
        p.distance_km != null ? `${p.distance_km} km away` : "",
        p.source_url ? `<a href="${p.source_url}" target="_blank" rel="noreferrer">Official source</a>` : "",
      ]
        .filter(Boolean)
        .join("<br/>");
      L.marker([p.latitude as number, p.longitude as number], { icon }).addTo(map).bindPopup(html);
    });

    setTimeout(() => map.invalidateSize(), 200);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [userLat, userLon, partners, radiusKm]);

  return (
    <div>
      <div ref={ref} className="map-wrap" />
      <p className="text-sm text-muted mt-2">
        Interactive OpenStreetMap. Partner pins appear only when coordinates are available from an official source.
      </p>
    </div>
  );
}
