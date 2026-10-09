from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class RideStatus(str, Enum):
    OPEN = "OPEN"
    BIDDING = "BIDDING"
    ACCEPTED = "ACCEPTED"
    EN_ROUTE = "EN_ROUTE"
    TRIP_STARTED = "TRIP_STARTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class VehicleCategory(str, Enum):
    BIKE = "BIKE"
    AUTO = "AUTO"
    ECONOMY = "ECONOMY"
    COMFORT = "COMFORT"
    EXECUTIVE = "EXECUTIVE"
    INTERCITY_AC = "INTERCITY_AC"

class UserRole(str, Enum):
    PASSENGER = "PASSENGER"
    CAPTAIN = "CAPTAIN"

class SignupRequest(BaseModel):
    role: UserRole
    name: str
    phone: str
    email: str
    password: str
    city: str = "Lahore"
    vehicle: Optional[str] = None
    plate_number: Optional[str] = None
    cnic: Optional[str] = None

class LoginRequest(BaseModel):
    identifier: str  # email or phone
    password: str

class UserProfile(BaseModel):
    id: str
    role: str
    name: str
    phone: str
    email: str
    city: str
    vehicle: Optional[str] = None
    plate_number: Optional[str] = None
    cnic: Optional[str] = None
    avatar: str
    rating: float = 5.0
    created_at: str

class Bid(BaseModel):
    id: str
    ride_id: str
    captain_name: str
    captain_avatar: str
    phone: str
    vehicle: str
    rating: float
    trips_count: int
    amount: int
    eta_mins: int
    distance_km: float
    timestamp: str

class Location(BaseModel):
    name: str
    lat: float
    lng: float

class CreateRideRequest(BaseModel):
    pickup_name: str
    pickup_lat: float
    pickup_lng: float
    destination_name: str
    destination_lat: float
    destination_lng: float
    passenger_name: str = "Passenger"
    passenger_phone: str = "+92 300 1234567"
    offer_amount: int
    vehicle_category: str = "COMFORT"
    passenger_seats: int = 1
    notes: Optional[str] = None

class CreateCaptainTripRequest(BaseModel):
    origin_name: str
    origin_lat: float
    origin_lng: float
    destination_name: str
    destination_lat: float
    destination_lng: float
    captain_name: str
    phone: str
    vehicle: str
    departure_time: str
    available_seats: int = 3
    seat_price: int
    notes: Optional[str] = None

class CaptainTrip(BaseModel):
    id: str
    origin: Location
    destination: Location
    captain_name: str
    captain_avatar: str
    phone: str
    vehicle: str
    rating: float
    departure_time: str
    available_seats: int
    seat_price: int
    notes: Optional[str] = None
    created_at: str

class Ride(BaseModel):
    id: str
    pickup: Location
    destination: Location
    passenger_name: str
    passenger_phone: str
    passenger_offer: int
    vehicle_category: str
    passenger_seats: int
    distance_km: float
    estimated_duration_mins: int
    status: RideStatus = RideStatus.OPEN
    bids: List[Bid] = []
    accepted_bid: Optional[Bid] = None
    created_at: str
    notes: Optional[str] = None
