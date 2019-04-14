/*
global
call: false
changeMarker: false
connectionParametersModal: false
createNode: false
currentView: true
deleteAll: false
deviceAutomationModal: false
displayPool: false
doc: false
partial: false
selected: false
showModal: false
showTypePanel: false
switchLayer: false
switchView: false
*/

/**
 * Display sites (pools with non-empty coordinates).
 */
function displaySites() {
  $(".menu").hide();
  deleteAll();
  call("/get_all/pool", function(pools) {
    for (let i = 0; i < pools.length; i++) {
      if (pools[i].longitude) {
        createNode(pools[i], "site");
      }
    }
  });
  $(".geo-menu").show();
}

/**
 * Enter site.
 * @param {siteId} siteId - Pool ID.
 */
function enterSite(siteId) {
  $(".menu").hide();
  $(".btn-view").show();
  $(".insite-menu,rc-device-menu,rc-link-menu").show();
  call(`/inventory/pool_objects/${siteId}`, function(objects) {
    displayPool(siteId, objects.devices, objects.links);
  });
}

/**
 * Update view.
 */
// eslint-disable-next-line
function updateView() {
  displaySites();
}

(function() {
  doc("https://enms.readthedocs.io/en/latest/views/geographical_view.html");
  switchView(currentView);
})();
