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
  centerLabel = "Your search location",
  mapHint,
}: {
  userLat: number;
  userLon: number;
  partners: Partner[];
  radiusKm?: number | null;
  centerLabel?: string;
  mapHint?: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;

    let cancelled = false;
    const map = L.map(ref.current).setView([userLat, userLon], radiusKm && radiusKm <= 40 ? 10 : 8);

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

    L.marker([userLat, userLon], { icon }).addTo(map).bindPopup(`<strong>${centerLabel}</strong>`);

    if (radiusKm) {
      L.circle([userLat, userLon], {
        radius: radiusKm * 1000,
        color: "#0b3a5b",
        fillOpacity: 0.08,
      }).addTo(map);
    }

    partners
      .filter((p) => p.latitude != null && p.longitude != null)
      .forEach((p) => {
        const html = [
          `<strong>${p.name}</strong>`,
          [p.district, p.state].filter(Boolean).join(", "),
          p.distance_km != null ? `${p.distance_km} km` : "",
          p.source_url ? `<a href="${p.source_url}" target="_blank" rel="noreferrer">Source</a>` : "",
        ]
          .filter(Boolean)
          .join("<br/>");
        L.marker([p.latitude as number, p.longitude as number], { icon }).addTo(map).bindPopup(html);
      });

    const timer = window.setTimeout(() => {
      if (cancelled) return;
      try {
        map.invalidateSize();
      } catch {
        // Map may already be removed during fast remounts
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      try {
        map.remove();
      } catch {
        // ignore double-remove
      }
    };
  }, [userLat, userLon, partners, radiusKm, centerLabel]);

  return (
    <div>
      <div ref={ref} className="map-wrap" />
      <p className="text-sm text-muted mt-2">
        {mapHint ||
          "Interactive OpenStreetMap. Partner pins appear only when coordinates are available from an official source."}
      </p>
    </div>
  );
}
