const mapContainer = document.getElementById("roof-map");
if (mapContainer) {
	const map = L.map("roof-map").setView([20.5937, 78.9629], 5);

	L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
		maxZoom: 20,
		attribution: "© OpenStreetMap",
	}).addTo(map);

	if (navigator.geolocation) {
		navigator.geolocation.getCurrentPosition((position) => {
			const { latitude, longitude } = position.coords;
			map.setView([latitude, longitude], 18);
		});
	}

	const drawnItems = new L.FeatureGroup();
	map.addLayer(drawnItems);

	const drawControl = new L.Control.Draw({
		edit: {
			featureGroup: drawnItems,
			edit: false,
			remove: true,
		},
		draw: {
			polygon: true,
			polyline: false,
			rectangle: true,
			circle: false,
			marker: false,
			circlemarker: false,
		},
	});
	map.addControl(drawControl);

	const polygonInput = document.getElementById("polygon_coords");

	const syncPolygon = (layer) => {
		if (!polygonInput) {
			return;
		}
		const latLngs = layer.getLatLngs()[0] || [];
		const coords = latLngs.map((point) => [point.lat, point.lng]);
		polygonInput.value = JSON.stringify(coords);
	};

	map.on(L.Draw.Event.CREATED, (event) => {
		drawnItems.clearLayers();
		drawnItems.addLayer(event.layer);
		syncPolygon(event.layer);
	});

	map.on(L.Draw.Event.DELETED, () => {
		if (polygonInput) {
			polygonInput.value = "";
		}
	});
}
