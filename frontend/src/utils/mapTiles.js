import L from 'leaflet'

// OpenStreetMap only has light tiles: in the dark theme they are recoloured on this map's
// own tile pane (not a global CSS rule, so maps that don't use this helper are untouched).
const DARK_TILE_FILTER = 'invert(1) hue-rotate(180deg) brightness(0.95) contrast(0.9)'

// OpenStreetMap tiles (CARTO basemaps started refusing our requests, 2026-10). OSM's
// tile policy requires the attribution to stay visible.
export function addOsmTiles(map) {
    // Plain "Leaflet" prefix: the default one carries a flag icon, which has no place on a VN-registered marketplace.
    map.attributionControl?.setPrefix('<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>')
    if (document.documentElement.getAttribute('data-theme') === 'dark') {
        map.getPane('tilePane').style.filter = DARK_TILE_FILTER
    }
    return L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    }).addTo(map)
}
