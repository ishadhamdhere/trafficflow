
const laneNames = ["North", "South", "East", "West"];
const laneNumbers = { North: 1, South: 2, East: 3, West: 4 };
const vehicleNumbers = { Car: 1, Bus: 2, Bike: 3 };
const carIcons = { Car: "🚗", Bus: "🚌", Bike: "🏍️" };

let lanes = {};
let passed = {};
let lastServed = -1;
let activeLane = null;
let movementTimers = {};

const $ = id => document.getElementById(id);

async function apiRequest(url, data = null) {
    const options = {
        method: data === null ? "GET" : "POST",
        headers: {}
    };

    if (data !== null) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(data);
    }

    const response = await fetch(url, options);
    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || result.message || "Request failed.");
    }

    return result;
}

function showMessage(message) {
    $("signalMessage").textContent = message;
}

function normalizeState(state) {
    if (!state || !Array.isArray(state.lanes)) {
        throw new Error("The backend returned an invalid traffic state.");
    }

    lanes = {};
    passed = {};

    state.lanes.forEach(item => {
        lanes[item.name] = item.vehicles || [];
        passed[item.name] = Number(item.passed) || 0;
    });

    lastServed = Number(state.lastServed);
    if (!Number.isFinite(lastServed)) lastServed = -1;
}

function setSignal(lane) {
    if (!laneNames.includes(lane)) return;

    activeLane = lane;

    laneNames.forEach(name => {
        const signal = $("signal" + name);
        if (!signal) return;

        signal.querySelectorAll(".light").forEach(light => {
            light.classList.remove("active");
        });

        const color = name === lane ? "green" : "red";
        const light = signal.querySelector("." + color);

        if (light) light.classList.add("active");
    });

    $("activeSignal").textContent = lane;
    showMessage(lane + " lane has GREEN. All other lanes have RED.");
}

function animateVehicle(lane) {
    const car = $("car" + lane);
    if (!car) return;

    clearTimeout(movementTimers[lane]);
    car.classList.remove("moving");

    // Restart the transition from the original position.
    void car.offsetWidth;

    car.classList.add("moving");

    movementTimers[lane] = setTimeout(() => {
        car.classList.remove("moving");
    }, 1500);
}

function updateIntersectionVehicles() {
    laneNames.forEach(lane => {
        const car = $("car" + lane);
        if (!car) return;

        const vehicles = lanes[lane] || [];

        if (vehicles.length > 0) {
            const firstVehicle = vehicles[0];
            car.textContent = carIcons[firstVehicle.type] || "🚗";
            car.title = "Vehicle " + firstVehicle.id + " waiting in " + lane + " lane";
            car.style.opacity = "1";
        } else {
            car.textContent = "🚘";
            car.title = "No vehicles waiting in " + lane + " lane";
            car.style.opacity = "0.45";
        }
    });
}

function refreshDashboard() {
    let totalWaiting = 0;
    let totalPassed = 0;
    let busiest = "None";
    let maximum = 0;

    laneNames.forEach(lane => {
        const vehicles = lanes[lane] || [];
        totalWaiting += vehicles.length;
        totalPassed += passed[lane] || 0;

        if (vehicles.length > maximum) {
            maximum = vehicles.length;
            busiest = lane;
        }
    });

    $("totalWaiting").textContent = totalWaiting;
    $("totalPassed").textContent = totalPassed;
    $("busiestLane").textContent = busiest;

    if (!activeLane) {
        $("activeSignal").textContent = "None";
    }

    $("queueGrid").innerHTML = laneNames.map(lane => {
        const vehicles = lanes[lane] || [];

        const items = vehicles.length
            ? vehicles.map((vehicle, index) =>
                `<div class="vehicle-item">${index + 1}. ${carIcons[vehicle.type] || "🚗"} #${vehicle.id} · ${vehicle.type}</div>`
            ).join("")
            : '<div class="vehicle-item">Queue is empty</div>';

        return `
            <div class="queue-card">
                <h4>${lane} Lane</h4>
                <div class="queue-count">${vehicles.length}</div>
                <p>${vehicles.length === 1 ? "vehicle" : "vehicles"} waiting</p>
                ${items}
            </div>
        `;
    }).join("");

    updateIntersectionVehicles();
}

async function loadStatus() {
    const state = await apiRequest("/api/status");
    normalizeState(state);
    refreshDashboard();
}

async function performAction(url, data) {
    try {
        const result = await apiRequest(url, data);

        if (result.state) {
            normalizeState(result.state);
        } else {
            await loadStatus();
        }

        refreshDashboard();

        if (result.ok) {
            if (result.selectedLane) {
                setSignal(result.selectedLane);
            }

            showMessage(result.message || "Action completed successfully.");
        } else {
            showMessage(result.message || "The action could not be completed.");
        }

        return result;
    } catch (error) {
        showMessage("Error: " + error.message);
        alert("Backend error: " + error.message);
        return null;
    }
}

$("vehicleForm").addEventListener("submit", async event => {
    event.preventDefault();

    const id = Number($("vehicleId").value);
    const type = $("vehicleType").value;
    const lane = $("vehicleLane").value;

    if (!Number.isSafeInteger(id) || id <= 0) {
        alert("Enter a valid positive vehicle ID.");
        return;
    }

    if (!laneNumbers[lane] || !vehicleNumbers[type]) {
        alert("Select a valid lane and vehicle type.");
        return;
    }

    const result = await performAction("/api/add", {
        id,
        type: vehicleNumbers[type],
        lane: laneNumbers[lane]
    });

    if (result && result.ok) {
        $("vehicleId").value = "";
        showMessage("Vehicle " + id + " added to " + lane + " lane.");
    }
});

async function passVehicle(lane) {
    if (!lane || !laneNumbers[lane]) {
        alert("Select a valid lane first.");
        return;
    }

    const result = await performAction("/api/signal", {
        lane: laneNumbers[lane]
    });

    if (result && result.ok) {
        animateVehicle(lane);

        const vehicle = result.vehicle;

        if (vehicle) {
            showMessage(
                "Vehicle " + vehicle.id + " (" + vehicle.type +
                ") passed through " + lane + " lane."
            );
        }
    }
}

$("autoBtn").addEventListener("click", async () => {
    const result = await performAction("/api/automatic", {});

    if (result && result.ok && result.selectedLane) {
        activeLane = result.selectedLane;
    }
});

$("manualBtn").addEventListener("click", async () => {
    const input = prompt("Choose a lane: North, South, East or West");

    if (input === null) return;

    const selected = input.trim().toLowerCase();
    const lane = laneNames.find(name => name.toLowerCase() === selected);

    if (!lane) {
        alert("Please enter North, South, East or West.");
        return;
    }

    activeLane = lane;
    setSignal(lane);
    await passVehicle(lane);
});

$("passBtn").addEventListener("click", async () => {
    if (!activeLane) {
        alert("Choose a manual or automatic signal first.");
        return;
    }

    await passVehicle(activeLane);
});

$("searchForm").addEventListener("submit", async event => {
    event.preventDefault();

    const id = Number($("searchId").value);

    if (!Number.isSafeInteger(id) || id <= 0) {
        $("searchResult").textContent = "Enter a valid positive vehicle ID.";
        return;
    }

    try {
        const result = await apiRequest("/api/search", { id });

        if (result.vehicle) {
            const vehicle = result.vehicle;
            const lane = result.vehicleLane || result.lane || "Unknown";

            $("searchResult").textContent =
                `Vehicle ${vehicle.id} found: ${vehicle.type}, ${lane} Lane, Waiting.`;
        } else {
            $("searchResult").textContent =
                result.message || "Vehicle not found in the waiting queues.";
        }

        if (result.state) {
            normalizeState(result.state);
            refreshDashboard();
        }
    } catch (error) {
        $("searchResult").textContent = "Error: " + error.message;
    }
});

$("refreshBtn").addEventListener("click", async () => {
    try {
        await loadStatus();
        showMessage("Dashboard refreshed from the C traffic engine.");
    } catch (error) {
        showMessage("Could not refresh: " + error.message);
    }
});

loadStatus().catch(error => {
    showMessage("Could not connect to the backend: " + error.message);
});
