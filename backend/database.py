import sqlite3
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import bcrypt

logger = logging.getLogger("safar.database")
DB_PATH = Path(__file__).parent.parent / "safar_marketplace.db"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def init_db():
    """Initialize SQLite database schema for users, rides, captain trips, and bids."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table: users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        role TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        city TEXT DEFAULT 'Lahore',
        vehicle TEXT,
        plate_number TEXT,
        cnic TEXT,
        avatar TEXT,
        rating REAL DEFAULT 5.0,
        created_at TEXT NOT NULL
    );
    """)
    
    # Table: rides (Passenger requests)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rides (
        id TEXT PRIMARY KEY,
        pickup_name TEXT,
        pickup_lat REAL,
        pickup_lng REAL,
        destination_name TEXT,
        destination_lat REAL,
        destination_lng REAL,
        passenger_name TEXT,
        passenger_phone TEXT,
        passenger_offer INTEGER,
        vehicle_category TEXT,
        passenger_seats INTEGER,
        distance_km REAL,
        estimated_duration_mins INTEGER,
        status TEXT,
        notes TEXT,
        created_at TEXT,
        accepted_bid_json TEXT
    );
    """)

    # Table: captain_trips (Captain scheduled routes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS captain_trips (
        id TEXT PRIMARY KEY,
        origin_name TEXT,
        origin_lat REAL,
        origin_lng REAL,
        destination_name TEXT,
        destination_lat REAL,
        destination_lng REAL,
        captain_name TEXT,
        captain_avatar TEXT,
        phone TEXT,
        vehicle TEXT,
        rating REAL,
        departure_time TEXT,
        available_seats INTEGER,
        seat_price INTEGER,
        notes TEXT,
        created_at TEXT
    );
    """)

    # Table: bids
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bids (
        id TEXT PRIMARY KEY,
        ride_id TEXT,
        captain_name TEXT,
        captain_avatar TEXT,
        phone TEXT,
        vehicle TEXT,
        rating REAL,
        trips_count INTEGER,
        amount INTEGER,
        eta_mins INTEGER,
        distance_km REAL,
        timestamp TEXT,
        FOREIGN KEY (ride_id) REFERENCES rides (id)
    );
    """)

    conn.commit()
    conn.close()

    seed_default_users()

def seed_default_users():
    """Seeds default demo Passenger and Captain accounts if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE email = 'passenger@safar.pk'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (id, role, name, email, phone, password_hash, city, avatar, rating, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "USR-" + str(uuid.uuid4())[:8].upper(),
            "PASSENGER",
            "Faheem Khan",
            "passenger@safar.pk",
            "+92 300 8899776",
            hash_password("password123"),
            "Lahore",
            "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=160&q=80",
            4.95,
            datetime.utcnow().isoformat()
        ))
    
    cursor.execute("SELECT id FROM users WHERE email = 'captain@safar.pk'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (id, role, name, email, phone, password_hash, city, vehicle, plate_number, cnic, avatar, rating, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "CAP-" + str(uuid.uuid4())[:8].upper(),
            "CAPTAIN",
            "Captain Tariq Khan",
            "captain@safar.pk",
            "+92 301 5544332",
            hash_password("password123"),
            "Islamabad",
            "Toyota Corolla (SE-412)",
            "LEA-2024",
            "35201-1234567-1",
            "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?auto=format&fit=crop&w=160&q=80",
            4.90,
            datetime.utcnow().isoformat()
        ))
    
    conn.commit()
    conn.close()

def save_ride(ride: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO rides (
        id, pickup_name, pickup_lat, pickup_lng, destination_name, destination_lat, destination_lng,
        passenger_name, passenger_phone, passenger_offer, vehicle_category, passenger_seats,
        distance_km, estimated_duration_mins, status, notes, created_at, accepted_bid_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ride["id"],
        ride["pickup"]["name"], ride["pickup"]["lat"], ride["pickup"]["lng"],
        ride["destination"]["name"], ride["destination"]["lat"], ride["destination"]["lng"],
        ride["passenger_name"], ride["passenger_phone"], ride["passenger_offer"],
        ride["vehicle_category"], ride["passenger_seats"], ride["distance_km"],
        ride["estimated_duration_mins"], ride["status"], ride["notes"],
        ride["created_at"], json.dumps(ride.get("accepted_bid")) if ride.get("accepted_bid") else None
    ))
    conn.commit()
    conn.close()

def save_captain_trip(trip: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO captain_trips (
        id, origin_name, origin_lat, origin_lng, destination_name, destination_lat, destination_lng,
        captain_name, captain_avatar, phone, vehicle, rating, departure_time, available_seats, seat_price, notes, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trip["id"], trip["origin"]["name"], trip["origin"]["lat"], trip["origin"]["lng"],
        trip["destination"]["name"], trip["destination"]["lat"], trip["destination"]["lng"],
        trip["captain_name"], trip["captain_avatar"], trip["phone"], trip["vehicle"],
        trip["rating"], trip["departure_time"], trip["available_seats"], trip["seat_price"],
        trip["notes"], trip["created_at"]
    ))
    conn.commit()
    conn.close()

def save_bid(bid: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO bids (
        id, ride_id, captain_name, captain_avatar, phone, vehicle, rating, trips_count, amount, eta_mins, distance_km, timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        bid["id"], bid["ride_id"], bid["captain_name"], bid["captain_avatar"], bid["phone"],
        bid["vehicle"], bid["rating"], bid["trips_count"], bid["amount"], bid["eta_mins"],
        bid["distance_km"], bid["timestamp"]
    ))
    conn.commit()
    conn.close()

def load_all_rides() -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM rides ORDER BY rowid DESC")
    rows = cursor.fetchall()
    rides = []
    
    for row in rows:
        r = dict(row)
        cursor.execute("SELECT * FROM bids WHERE ride_id = ?", (r["id"],))
        bids_rows = cursor.fetchall()
        bids = [dict(b) for b in bids_rows]
        
        accepted_bid = json.loads(r["accepted_bid_json"]) if r["accepted_bid_json"] else None
        
        ride_dict = {
            "id": r["id"],
            "pickup": {"name": r["pickup_name"], "lat": r["pickup_lat"], "lng": r["pickup_lng"]},
            "destination": {"name": r["destination_name"], "lat": r["destination_lat"], "lng": r["destination_lng"]},
            "passenger_name": r["passenger_name"],
            "passenger_phone": r["passenger_phone"],
            "passenger_offer": r["passenger_offer"],
            "vehicle_category": r["vehicle_category"],
            "passenger_seats": r["passenger_seats"],
            "distance_km": r["distance_km"],
            "estimated_duration_mins": r["estimated_duration_mins"],
            "status": r["status"],
            "notes": r["notes"] or "",
            "created_at": r["created_at"],
            "bids": bids,
            "accepted_bid": accepted_bid
        }
        rides.append(ride_dict)

    conn.close()
    return rides

def load_all_captain_trips() -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM captain_trips ORDER BY rowid DESC")
    rows = cursor.fetchall()
    trips = []
    
    for row in rows:
        t = dict(row)
        trip_dict = {
            "id": t["id"],
            "origin": {"name": t["origin_name"], "lat": t["origin_lat"], "lng": t["origin_lng"]},
            "destination": {"name": t["destination_name"], "lat": t["destination_lat"], "lng": t["destination_lng"]},
            "captain_name": t["captain_name"],
            "captain_avatar": t["captain_avatar"],
            "phone": t["phone"],
            "vehicle": t["vehicle"],
            "rating": t["rating"],
            "departure_time": t["departure_time"],
            "available_seats": t["available_seats"],
            "seat_price": t["seat_price"],
            "notes": t["notes"] or "",
            "created_at": t["created_at"]
        }
        trips.append(trip_dict)

    conn.close()
    return trips

def create_user_in_db(user_data: dict) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO users (
        id, role, name, email, phone, password_hash, city, vehicle, plate_number, cnic, avatar, rating, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_data["id"],
        user_data["role"],
        user_data["name"],
        user_data["email"].lower().strip(),
        user_data["phone"].strip(),
        user_data["password_hash"],
        user_data.get("city", "Lahore"),
        user_data.get("vehicle"),
        user_data.get("plate_number"),
        user_data.get("cnic"),
        user_data.get("avatar") or "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=160&q=80",
        user_data.get("rating", 5.0),
        user_data["created_at"]
    ))
    conn.commit()
    conn.close()
    return user_data

def get_user_by_identifier(identifier: str) -> Optional[dict]:
    clean_id = identifier.lower().strip()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE LOWER(email) = ? OR phone = ?",
        (clean_id, identifier.strip())
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
