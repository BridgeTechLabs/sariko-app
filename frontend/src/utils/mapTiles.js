import L from 'leaflet'

// OpenStreetMap tiles (CARTO basemaps started refusing our requests, 2026-10). OSM's
// tile policy requires the attribution to stay visible. Dark theme recolours the tile
// pane in assets/main.css instead of switching tile sets.
export function addOsmTiles(map) {
    // Plain "Leaflet" prefix: the default one carries a flag icon, which has no place on a VN-registered marketplace.
    map.attributionControl?.setPrefix('<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>')
    return L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    }).addTo(map)
}
