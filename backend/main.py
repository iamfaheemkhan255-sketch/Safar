import asyncio
import json
import logging
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import uuid
from typing import Optional, List, Dict
from datetime import datetime
from backend.models import (
    CreateRideRequest, CreateCaptainTripRequest, SignupRequest, LoginRequest,
    CreateBidRequest, AcceptBidRequest
)
from backend.database import (
    hash_password, verify_password, create_user_in_db,
    get_user_by_identifier, get_user_by_id
)
from backend.store import store, PAKISTAN_CITIES
from backend.manager import manager
from backend.simulator import trigger_simulated_bids_for_ride, simulate_ride_progress

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("safar.main")

app = FastAPI(
    title="Safar Real-Time Ride-Sharing & Live Fare Bidding Engine",
    description="Production Python FastAPI + WebSockets Marketplace Platform",
    version="2.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HEALTH CHECK FOR CLOUD DEPLOYMENT ---

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Safar Mobility Engine"}

# --- AUTHENTICATION API ENDPOINTS ---

@app.post("/api/auth/signup")
def auth_signup(req: SignupRequest):
    """Register a new Passenger or Captain with role-locked account."""
    existing = get_user_by_identifier(req.email) or get_user_by_identifier(req.phone)
    if existing:
        raise HTTPException(status_code=400, detail="Account with this email or phone already exists")
    
    role_val = req.role.value if hasattr(req.role, "value") else str(req.role)
    prefix = "CAP-" if role_val == "CAPTAIN" else "USR-"
    user_id = prefix + str(uuid.uuid4())[:8].upper()
    avatar = (
        "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?auto=format&fit=crop&w=160&q=80"
        if role_val == "CAPTAIN"
        else "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=160&q=80"
    )
    
    user_data = {
        "id": user_id,
        "role": role_val,
        "name": req.name,
        "email": req.email,
        "phone": req.phone,
        "password_hash": hash_password(req.password),
        "city": req.city,
        "vehicle": req.vehicle,
        "plate_number": req.plate_number,
        "cnic": req.cnic,
        "avatar": avatar,
        "rating": 5.0,
        "created_at": datetime.utcnow().isoformat()
    }
    create_user_in_db(user_data)
    profile = {k: v for k, v in user_data.items() if k != "password_hash"}
    return {"status": "success", "user": profile}

@app.post("/api/auth/login")
def auth_login(req: LoginRequest):
    """Authenticate user by email or phone and return user profile."""
    user = get_user_by_identifier(req.identifier)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email/phone or password")
    
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email/phone or password")
    
    profile = {k: v for k, v in user.items() if k != "password_hash"}
    return {"status": "success", "user": profile}

@app.get("/api/auth/me")
def auth_me(user_id: str):
    """Retrieve logged in user profile."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    profile = {k: v for k, v in user.items() if k != "password_hash"}
    return {"status": "success", "user": profile}

# --- REST API ENDPOINTS ---

@app.get("/api/cities")
def get_cities():
    """Returns list of Pakistani cities with geographical coordinates."""
    return PAKISTAN_CITIES

@app.get("/api/rides")
def get_active_rides():
    """Returns all active passenger ride requests."""
    return store.get_all_rides()

@app.get("/api/captain-trips")
def get_captain_trips():
    """Returns all scheduled Captain trips available for booking."""
    return store.get_all_captain_trips()

@app.post("/api/captain-trips")
async def create_captain_trip(req: CreateCaptainTripRequest):
    trip = store.create_captain_trip(req)
    await manager.broadcast({
        "type": "NEW_CAPTAIN_TRIP",
        "trip": trip
    })
    await manager.broadcast({
        "type": "CAPTAIN_TRIP_CREATED",
        "trip": trip
    })
    return trip

@app.post("/api/rides")
async def create_ride(req: CreateRideRequest, background_tasks: BackgroundTasks):
    ride = store.create_ride(req)
    await manager.broadcast({
        "type": "NEW_RIDE_REQUEST",
        "ride": ride
    })
    await manager.broadcast({
        "type": "RIDE_CREATED",
        "ride": ride
    })

    if store.simulator_active:
        background_tasks.add_task(trigger_simulated_bids_for_ride, ride["id"])
    return ride

@app.post("/api/rides/{ride_id}/bid")
async def submit_bid(ride_id: str, req: CreateBidRequest):
    phone = req.captain_phone or req.phone or "+92 300 9988776"
    avatar = req.captain_avatar or "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=150&q=80"
    bid = store.add_bid(
        ride_id=ride_id,
        captain_name=req.captain_name or "Captain",
        captain_avatar=avatar,
        phone=phone,
        vehicle=req.vehicle or "Toyota Corolla",
        rating=float(req.rating or 4.9),
        trips_count=int(req.trips_count or 1250),
        amount=int(req.amount),
        eta_mins=int(req.eta_mins or 5),
        distance_km=float(req.distance_km or 2.4)
    )
    if not bid:
        raise HTTPException(status_code=404, detail="Ride not found")

    ride = store.get_ride(ride_id)
    msg = {
        "type": "NEW_BID",
        "ride_id": ride_id,
        "bid": bid,
        "all_bids": ride["bids"],
        "ride": ride
    }
    await manager.broadcast(msg)
    await manager.broadcast({**msg, "type": "BID_RECEIVED"})
    return bid

@app.post("/api/rides/{ride_id}/accept")
@app.post("/api/rides/{ride_id}/accept-bid")
async def accept_bid(ride_id: str, background_tasks: BackgroundTasks, req: Optional[AcceptBidRequest] = None, bid_id: Optional[str] = None):
    target_bid_id = (req.bid_id if req else None) or bid_id
    if not target_bid_id:
        raise HTTPException(status_code=400, detail="bid_id is required")

    ride = store.accept_bid(ride_id, target_bid_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride or Bid not found")

    await manager.broadcast({
        "type": "BID_ACCEPTED",
        "ride_id": ride_id,
        "bid_id": target_bid_id,
        "ride": ride
    })

    if store.simulator_active:
        background_tasks.add_task(simulate_ride_progress, ride_id)
    return ride

@app.post("/api/simulator/toggle")
async def toggle_simulator(active: bool):
    store.simulator_active = active
    await manager.broadcast({
        "type": "SIMULATOR_TOGGLED",
        "active": active
    })
    return {"simulator_active": store.simulator_active}

# --- WEBSOCKET REAL-TIME ENDPOINT ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Send initial state immediately upon connection
    await manager.send_personal_message({
        "type": "INITIAL_STATE",
        "rides": store.get_all_rides(),
        "captain_trips": store.get_all_captain_trips(),
        "cities": PAKISTAN_CITIES,
        "simulator_active": store.simulator_active,
        "captain_locations": store.captain_locations
    }, websocket)

    try:
        while True:
            data_raw = await websocket.receive_text()
            data = json.loads(data_raw)
            msg_type = data.get("type")

            # 1. PASSENGER CREATES RIDE REQUEST
            if msg_type == "CREATE_RIDE":
                req_data = CreateRideRequest(
                    pickup_name=data["pickup_name"],
                    pickup_lat=float(data["pickup_lat"]),
                    pickup_lng=float(data["pickup_lng"]),
                    destination_name=data["destination_name"],
                    destination_lat=float(data["destination_lat"]),
                    destination_lng=float(data["destination_lng"]),
                    passenger_name=data.get("passenger_name", "Passenger"),
                    passenger_phone=data.get("passenger_phone", "+92 300 1234567"),
                    offer_amount=int(data["offer_amount"]),
                    vehicle_category=data.get("vehicle_category", "COMFORT"),
                    passenger_seats=int(data.get("passenger_seats", 1)),
                    notes=data.get("notes", "")
                )
                ride = store.create_ride(req_data)

                await manager.broadcast({
                    "type": "RIDE_CREATED",
                    "ride": ride
                })

                if store.simulator_active:
                    asyncio.create_task(trigger_simulated_bids_for_ride(ride["id"]))

            # 2. CAPTAIN CREATES SCHEDULED TRIP POST
            elif msg_type == "CREATE_CAPTAIN_TRIP":
                req_trip = CreateCaptainTripRequest(
                    origin_name=data["origin_name"],
                    origin_lat=float(data["origin_lat"]),
                    origin_lng=float(data["origin_lng"]),
                    destination_name=data["destination_name"],
                    destination_lat=float(data["destination_lat"]),
                    destination_lng=float(data["destination_lng"]),
                    captain_name=data.get("captain_name", "Captain Tariq Mehmood"),
                    phone=data.get("phone", "+92 300 4455667"),
                    vehicle=data.get("vehicle", "Toyota Corolla 2021 (SE-412)"),
                    departure_time=data.get("departure_time", "Today @ 5:00 PM"),
                    available_seats=int(data.get("available_seats", 3)),
                    seat_price=int(data["seat_price"]),
                    notes=data.get("notes", "")
                )
                trip = store.create_captain_trip(req_trip)

                await manager.broadcast({
                    "type": "CAPTAIN_TRIP_CREATED",
                    "trip": trip
                })

            # 3. CAPTAIN SUBMIT BID ON PASSENGER REQUEST
            elif msg_type == "SUBMIT_BID":
                ride_id = data["ride_id"]
                bid = store.add_bid(
                    ride_id=ride_id,
                    captain_name=data.get("captain_name", "Captain Tariq"),
                    captain_avatar=data.get("captain_avatar", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=150&q=80"),
                    phone=data.get("phone", "+92 300 9988776"),
                    vehicle=data.get("vehicle", "Toyota Corolla (SE-412)"),
                    rating=float(data.get("rating", 4.9)),
                    trips_count=int(data.get("trips_count", 1250)),
                    amount=int(data["amount"]),
                    eta_mins=int(data.get("eta_mins", 5)),
                    distance_km=float(data.get("distance_km", 3.2))
                )
                
                if bid:
                    ride = store.get_ride(ride_id)
                    await manager.broadcast({
                        "type": "BID_RECEIVED",
                        "ride_id": ride_id,
                        "bid": bid,
                        "all_bids": ride["bids"],
                        "ride": ride
                    })

            # 4. PASSENGER ACCEPTS BID
            elif msg_type == "ACCEPT_BID":
                ride_id = data["ride_id"]
                bid_id = data["bid_id"]
                ride = store.accept_bid(ride_id, bid_id)
                if ride:
                    await manager.broadcast({
                        "type": "BID_ACCEPTED",
                        "ride_id": ride_id,
                        "bid_id": bid_id,
                        "ride": ride
                    })
                    if store.simulator_active:
                        asyncio.create_task(simulate_ride_progress(ride_id))

            # 5. UPDATE RIDE STATUS
            elif msg_type == "UPDATE_STATUS":
                ride_id = data["ride_id"]
                status = data["status"]
                ride = store.update_status(ride_id, status)
                if ride:
                    await manager.broadcast({
                        "type": "RIDE_STATUS_UPDATED",
                        "ride_id": ride_id,
                        "status": status,
                        "ride": ride
                    })

            # 6. CAPTAIN LIVE GPS LOCATION TRANSMISSION
            elif msg_type == "UPDATE_CAPTAIN_LOCATION":
                c_id = data["captain_id"]
                c_name = data.get("captain_name", "Captain Tariq")
                lat = float(data["lat"])
                lng = float(data["lng"])
                vehicle = data.get("vehicle", "Toyota Corolla")
                
                store.update_captain_location(c_id, c_name, lat, lng, vehicle)
                await manager.broadcast({
                    "type": "CAPTAIN_LOCATION_UPDATED",
                    "captain_id": c_id,
                    "captain_name": c_name,
                    "lat": lat,
                    "lng": lng,
                    "vehicle": vehicle
                })

            # 7. TOGGLE SIMULATOR
            elif msg_type == "TOGGLE_SIMULATOR":
                store.simulator_active = bool(data["active"])
                await manager.broadcast({
                    "type": "SIMULATOR_TOGGLED",
                    "active": store.simulator_active
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- SERVE FRONTEND HTML UI ---

static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    html_file = static_dir / "index.html"
    if html_file.exists():
        return FileResponse(
            str(html_file),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return HTMLResponse("<h1>Safar Real-Time Ride-Sharing Engine</h1><p>Frontend file missing.</p>")
