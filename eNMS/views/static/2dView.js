/*
global
enterPool: false
L: false
layers: false
link_colors: false
markersArray: true
parameters: false
polylinesArray: true
showTypeModal: false
subtype_sizes: false
view: false
*/

let markers;

const map = L.map('map').setView(
  [parameters.default_latitude, parameters.default_longitude],
  parameters.default_zoom_level
);

const osmLayer = L.tileLayer(layers['osm']);
map.addLayer(osmLayer);
let currentLayer = osmLayer;
if (view == '2DC') {
  markers = L.markerClusterGroup();
  map.addLayer(markers);
}

/**
 * Change the tile layer.
 * @param {layer} layer - tile layer.
 */
function switchLayer(layer) { // eslint-disable-line no-unused-vars
  map.removeLayer(currentLayer);
  currentLayer = L.tileLayer(layers[layer]);
  map.addLayer(currentLayer);
  $('.dropdown-submenu a.menu-layer').next('ul').toggle();
}

for (const [key, value] of Object.entries(subtype_sizes)) {
  window[`icon_${key}`] = L.icon({
    iconUrl: `static/images/2D/${key}.gif`,
    iconSize: value,
    iconAnchor: [9, 6],
    popupAnchor: [8, -5],
    });
}

L.PolylineClusterable = L.Polyline.extend({
  _originalInitialize: L.Polyline.prototype.initialize,
  initialize: function(bounds, options) {
    this._originalInitialize(bounds, options);
    this._latlng = this.getBounds().getCenter();
  },
  getLatLng: function() {
    return this._latlng;
  },
  setLatLng: function() {
  },
});

const routerIcon = window['icon_router'];

/**
 * Create a node (device or pool).
 * @param {node} node - Device or Pool.
 * @param {nodeType} nodeType - Device or Pool.
 */
function createNode(node, nodeType) { // eslint-disable-line no-unused-vars
  const marker = L.marker([node.latitude, node.longitude]);
  marker.node_id = node.id;
  if (nodeType === 'device') {
    marker.icon = window[`icon_${node.subtype}`] || routerIcon;
  } else {
    marker.icon = window['icon_site'];
  }
  marker.setIcon(marker.icon);
  markersArray.push(marker);
  marker.on('click', function(e) {
    if (nodeType == 'pool') {
      enterPool(this.node_id);
    } else {
      showTypeModal(nodeType, this.node_id);
    }
  });
  marker.on('contextmenu', function(e) {
    $('.menu').hide();
    $(`.rc-${nodeType}-menu`).show();
    selectedObject = this.node_id; // eslint-disable-line no-undef
  });
  marker.bindTooltip(node['name'], {permanent: false});
  if (view == '2D') {
    marker.addTo(map);
  } else {
    markers.addLayer(marker);
  }
}

/**
 * Create a link.
 * @param {link} link - Link.
 */
function createLink(link) { // eslint-disable-line no-unused-vars
  let pointA = new L.LatLng(
    link.source.latitude,
    link.source.longitude
  );
  let pointB = new L.LatLng(
    link.destination.latitude,
    link.destination.longitude
  );

  const pointList = [pointA, pointB];
  const polyline = new L.PolylineClusterable(pointList, {
    color: link_colors[link.subtype],
    weight: 3,
    opacity: 1,
    smoothFactor: 1,
  });
  polylinesArray.push(polyline);
  polyline.link_id = link.id;
  polyline.on('click', function(e) {
    showTypeModal('link', this.link_id);
  });
  polyline.on('contextmenu', function(e) {
    $('.menu').hide();
    $('.rc-link-menu').show();
    selectedObject = this.link_id; // eslint-disable-line no-undef
  });
  polyline.bindTooltip(link['name'], {
    permanent: false,
  });
  if (view == '2D') {
    polyline.addTo(map);
  } else {
    markers.addLayer(polyline);
  }
}

/**
 * Delete all devices and links on the map.
 */
function deleteAll() { // eslint-disable-line no-unused-vars
  for (let i = 0; i < markersArray.length; i++) {
    if (view == '2D') {
      markersArray[i].removeFrom(map);
    } else {
      markers.removeLayer(markersArray[i]);
    }
  }
  for (let i = 0; i < polylinesArray.length; i++) {
    if (view == '2D') {
      polylinesArray[i].removeFrom(map);
    } else {
      markers.removeLayer(polylinesArray[i]);
    }
  }
  markersArray = [];
  polylinesArray = [];
}
