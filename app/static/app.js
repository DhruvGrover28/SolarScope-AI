const mapContainer = document.getElementById("roof-map");
if (mapContainer) {
	const map = L.map("roof-map").setView([20.5937, 78.9629], 5);
	window.roofMap = map;

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

const greeting = document.getElementById("greeting");
if (greeting) {
	const hour = new Date().getHours();
	let label = "Good Evening";
	if (hour >= 5 && hour <= 11) {
		label = "Good Morning";
	} else if (hour >= 12 && hour <= 16) {
		label = "Good Afternoon";
	}
	const name = greeting.dataset.name || "there";
	greeting.textContent = `${label}, ${name} :)`;
}

const themeToggle = document.getElementById("theme-toggle");
const themeKey = "solarscope-theme";
const setTheme = (theme) => {
	if (theme === "dark") {
		document.body.classList.add("dark-mode");
		if (themeToggle) themeToggle.textContent = "☀️";
	} else {
		document.body.classList.remove("dark-mode");
		if (themeToggle) themeToggle.textContent = "🌙";
	}
	localStorage.setItem(themeKey, theme);
};

const savedTheme = localStorage.getItem(themeKey) || "light";
setTheme(savedTheme);

if (themeToggle) {
	themeToggle.addEventListener("click", () => {
		const nextTheme = document.body.classList.contains("dark-mode") ? "light" : "dark";
		setTheme(nextTheme);
	});
}

const methodSelect = document.getElementById("method-select");
const methodCards = document.querySelectorAll(".method-card");
const showMethod = (value) => {
	methodCards.forEach((card) => {
		const isActive = card.dataset.method === value;
		card.classList.toggle("is-active", isActive);
	});
	if (value === "polygon" && window.roofMap) {
		setTimeout(() => window.roofMap.invalidateSize(), 150);
	}
};

if (methodSelect) {
	showMethod(methodSelect.value);
	methodSelect.addEventListener("change", (event) => {
		showMethod(event.target.value);
	});
}

document.querySelectorAll(".avatar-carousel").forEach((carousel) => {
	const slides = carousel.querySelectorAll(".avatar-slide");
	const prev = carousel.querySelector("[data-dir='prev']");
	const next = carousel.querySelector("[data-dir='next']");
	let activeIndex = 0;
	slides.forEach((slide, index) => {
		if (slide.classList.contains("is-active")) {
			activeIndex = index;
		}
	});

	const updateActive = (index) => {
		activeIndex = (index + slides.length) % slides.length;
		slides.forEach((slide, idx) => {
			const isActive = idx === activeIndex;
			slide.classList.toggle("is-active", isActive);
			const radio = slide.querySelector("input[type='radio']");
			if (radio) radio.checked = isActive;
		});
	};

	if (prev) {
		prev.addEventListener("click", () => updateActive(activeIndex - 1));
	}
	if (next) {
		next.addEventListener("click", () => updateActive(activeIndex + 1));
	}
});

document.querySelectorAll(".toggle-password").forEach((button) => {
	button.addEventListener("click", () => {
		const input = button.parentElement.querySelector("input");
		if (!input) return;
		input.type = input.type === "password" ? "text" : "password";
	});
});
