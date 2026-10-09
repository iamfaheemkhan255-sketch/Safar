import math
import time
import random
import logging
from typing import Dict, List, Optional
from backend.models import Ride, Bid, Location, RideStatus, CreateRideRequest, CreateCaptainTripRequest
from backend.database import init_db, save_ride, save_bid, save_captain_trip, load_all_rides, load_all_captain_trips

logger = logging.getLogger("safar.store")

PAKISTAN_CITIES: Dict[str, dict] = {
    "Lahore": {"lat": 31.5204, "lng": 74.3587, "province": "Punjab"},
    "Islamabad": {"lat": 33.6844, "lng": 73.0479, "province": "Federal"},
    "Rawalpindi": {"lat": 33.5651, "lng": 73.0169, "province": "Punjab"},
    "Karachi": {"lat": 24.8607, "lng": 67.0011, "province": "Sindh"},
    "Faisalabad": {"lat": 31.4504, "lng": 73.1350, "province": "Punjab"},
    "Multan": {"lat": 30.1575, "lng": 71.5249, "province": "Punjab"},
    "Peshawar": {"lat": 34.0151, "lng": 71.5249, "province": "KPK"},
    "Quetta": {"lat": 30.1798, "lng": 66.9750, "province": "Balochistan"},
    "Murree": {"lat": 33.9070, "lng": 73.3943, "province": "Punjab"},
    "Sialkot": {"lat": 32.4945, "lng": 74.5229, "province": "Punjab"},
    "Gujranwala": {"lat": 32.1877, "lng": 74.1945, "province": "Punjab"},
    "Hyderabad": {"lat": 25.3960, "lng": 68.3578, "province": "Sindh"},
}

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

class MarketplaceStore:
    def __init__(self):
        init_db()
        self.rides: Dict[str, dict] = {}
        self.captain_trips: Dict[str, dict] = {}
        self.captain_locations: Dict[str, dict] = {}
        self.ride_counter: int = 1000
        self.trip_counter: int = 3000
        self.bid_counter: int = 5000
        self.simulator_active: bool = False
        self.load_from_database()

    def load_from_database(self):
        saved_rides = load_all_rides()
        if saved_rides:
            for r in saved_rides:
                self.rides[r["id"]] = r
                try:
                    num = int(r["id"].split("-")[1])
                    if num > self.ride_counter:
                        self.ride_counter = num
                except Exception:
                    pass

        saved_trips = load_all_captain_trips()
        if saved_trips:
            for t in saved_trips:
                self.captain_trips[t["id"]] = t
                try:
                    tnum = int(t["id"].split("-")[1])
                    if tnum > self.trip_counter:
                        self.trip_counter = tnum
                except Exception:
                    pass
        else:
            self.seed_initial_captain_trips()

    def seed_initial_captain_trips(self):
        """Seed sample Captain scheduled routes into database."""
        sample_trips = [
            {
                "origin_name": "Lahore (Thokar Niaz Baig)",
                "origin_lat": 31.4700,
                "origin_lng": 74.2400,
                "destination_name": "Islamabad (G-9 Markaz)",
                "destination_lat": 33.6900,
                "destination_lng": 73.0300,
                "captain_name": "Captain Tariq Mehmood",
                "phone": "+92 300 4455667",
                "vehicle": "Toyota Corolla 2021 (SE-412)",
                "departure_time": "Today @ 4:00 PM",
                "available_seats": 3,
                "seat_price": 1100,
                "notes": "AC Sedan, spacious boot space, non-smoking vehicle"
            },
            {
                "origin_name": "Islamabad (F-10 Markaz)",
                "origin_lat": 33.6950,
                "origin_lng": 73.0150,
                "destination_name": "Peshawar (Saddar)",
                "destination_lat": 34.0080,
                "destination_lng": 71.5300,
                "captain_name": "Captain Hamza Abbasi",
                "phone": "+92 321 8899223",
                "vehicle": "Honda Civic (LE-909)",
                "departure_time": "Today @ 6:30 PM",
                "available_seats": 2,
                "seat_price": 950,
                "notes": "M-1 Motorway route, fast & smooth ride"
            }
        ]
        for st in sample_trips:
            self.create_captain_trip(CreateCaptainTripRequest(**st))

    def get_all_rides(self) -> List[dict]:
        return list(self.rides.values())

    def get_all_captain_trips(self) -> List[dict]:
        return list(self.captain_trips.values())

    def get_ride(self, ride_id: str) -> Optional[dict]:
        return self.rides.get(ride_id)

    def create_ride(self, req: CreateRideRequest) -> dict:
        self.ride_counter += 1
        ride_id = f"RIDE-{self.ride_counter}"

        pickup_name = req.pickup_name or req.origin_city or "Lahore"
        dest_name = req.destination_name or req.dest_city or "Islamabad"
        offer = req.offer_amount if req.offer_amount is not None else (req.proposed_fare if req.proposed_fare is not None else 3000)

        p_coords = PAKISTAN_CITIES.get(pickup_name, {"lat": 31.5204, "lng": 74.3587})
        d_coords = PAKISTAN_CITIES.get(dest_name, {"lat": 33.6844, "lng": 73.0479})

        pickup_lat = req.pickup_lat if req.pickup_lat is not None else p_coords["lat"]
        pickup_lng = req.pickup_lng if req.pickup_lng is not None else p_coords["lng"]
        dest_lat = req.destination_lat if req.destination_lat is not None else d_coords["lat"]
        dest_lng = req.destination_lng if req.destination_lng is not None else d_coords["lng"]

        dist_km = haversine_distance(pickup_lat, pickup_lng, dest_lat, dest_lng)
        est_duration = max(15, int((dist_km / 65.0) * 60))

        pickup_obj = {"name": pickup_name, "lat": pickup_lat, "lng": pickup_lng}
        dest_obj = {"name": dest_name, "lat": dest_lat, "lng": dest_lng}

        ride_dict = {
            "id": ride_id,
            "pickup": pickup_obj,
            "origin": pickup_obj,
            "destination": dest_obj,
            "passenger_name": req.passenger_name,
            "passenger_phone": req.passenger_phone,
            "passenger_offer": int(offer),
            "proposed_fare": int(offer),
            "vehicle_category": req.vehicle_category,
            "passenger_seats": req.passenger_seats,
            "distance_km": dist_km,
            "estimated_duration_mins": est_duration,
            "status": RideStatus.OPEN.value,
            "bids": [],
            "accepted_bid": None,
            "created_at": time.strftime("%H:%M:%S"),
            "notes": req.notes or ""
        }
        self.rides[ride_id] = ride_dict
        save_ride(ride_dict)
        return ride_dict

    def create_captain_trip(self, req: CreateCaptainTripRequest) -> dict:
        self.trip_counter += 1
        trip_id = f"TRIP-{self.trip_counter}"

        origin_name = req.origin_name or req.origin_city or "Lahore"
        dest_name = req.destination_name or req.dest_city or "Islamabad"
        phone = req.phone or "+92 300 1234567"
        vehicle = req.vehicle or "Toyota Corolla"

        o_coords = PAKISTAN_CITIES.get(origin_name, {"lat": 31.4700, "lng": 74.2400})
        d_coords = PAKISTAN_CITIES.get(dest_name, {"lat": 33.6900, "lng": 73.0300})

        o_lat = req.origin_lat if req.origin_lat is not None else o_coords["lat"]
        o_lng = req.origin_lng if req.origin_lng is not None else o_coords["lng"]
        d_lat = req.destination_lat if req.destination_lat is not None else d_coords["lat"]
        d_lng = req.destination_lng if req.destination_lng is not None else d_coords["lng"]

        trip_dict = {
            "id": trip_id,
            "origin": {"name": origin_name, "lat": o_lat, "lng": o_lng},
            "destination": {"name": dest_name, "lat": d_lat, "lng": d_lng},
            "origin_city": origin_name,
            "dest_city": dest_name,
            "captain_name": req.captain_name,
            "captain_avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=150&q=80",
            "phone": phone,
            "vehicle": vehicle,
            "rating": req.rating or 4.9,
            "departure_time": req.departure_time,
            "available_seats": req.available_seats,
            "seat_price": req.seat_price,
            "notes": req.notes or "",
            "created_at": time.strftime("%H:%M:%S")
        }
        self.captain_trips[trip_id] = trip_dict
        save_captain_trip(trip_dict)
        return trip_dict

    def add_bid(self, ride_id: str, captain_name: str, captain_avatar: str, phone: str, vehicle: str, rating: float, trips_count: int, amount: int, eta_mins: int, distance_km: float) -> Optional[dict]:
        if ride_id not in self.rides:
            return None
        
        self.bid_counter += 1
        bid_dict = {
            "id": f"BID-{self.bid_counter}",
            "ride_id": ride_id,
            "captain_name": captain_name,
            "captain_avatar": captain_avatar,
            "phone": phone,
            "vehicle": vehicle,
            "rating": rating,
            "trips_count": trips_count,
            "amount": amount,
            "eta_mins": eta_mins,
            "distance_km": distance_km,
            "timestamp": time.strftime("%H:%M:%S")
        }
        
        self.rides[ride_id]["bids"].append(bid_dict)
        self.rides[ride_id]["status"] = RideStatus.BIDDING.value
        
        save_bid(bid_dict)
        save_ride(self.rides[ride_id])
        return bid_dict

    def accept_bid(self, ride_id: str, bid_id: str) -> Optional[dict]:
        if ride_id not in self.rides:
            return None
        
        ride = self.rides[ride_id]
        target_bid = next((b for b in ride["bids"] if b["id"] == bid_id), None)
        if not target_bid and ride["bids"]:
            target_bid = ride["bids"][0]
            
        if target_bid:
            ride["status"] = RideStatus.ACCEPTED.value
            ride["accepted_bid"] = target_bid
            if "origin" not in ride and "pickup" in ride:
                ride["origin"] = ride["pickup"]
            if "proposed_fare" not in ride and "passenger_offer" in ride:
                ride["proposed_fare"] = ride["passenger_offer"]
            save_ride(ride)
            return ride
        return None

    def update_status(self, ride_id: str, status: str) -> Optional[dict]:
        if ride_id in self.rides:
            self.rides[ride_id]["status"] = status
            save_ride(self.rides[ride_id])
            return self.rides[ride_id]
        return None

    def update_captain_location(self, captain_id: str, captain_name: str, lat: float, lng: float, vehicle: str):
        self.captain_locations[captain_id] = {
            "captain_id": captain_id,
            "captain_name": captain_name,
            "lat": lat,
            "lng": lng,
            "vehicle": vehicle,
            "last_updated": time.strftime("%H:%M:%S")
        }

store = MarketplaceStore()
