"""
Setup script for the sample e-commerce database.

Creates a SQLite database with:
- customers (50 rows)
- products (50 rows)
- orders (100 rows)
- order_items (200 rows)

Run this script to create/reset the sample database:
    python data/setup_sample_db.py
"""

import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "sample.db"

# Sample data
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"
]

CITIES = [
    ("New York", "NY"), ("Los Angeles", "CA"), ("Chicago", "IL"), ("Houston", "TX"),
    ("Phoenix", "AZ"), ("Philadelphia", "PA"), ("San Antonio", "TX"), ("San Diego", "CA"),
    ("Dallas", "TX"), ("San Jose", "CA"), ("Austin", "TX"), ("Jacksonville", "FL"),
    ("Fort Worth", "TX"), ("Columbus", "OH"), ("Charlotte", "NC"), ("San Francisco", "CA"),
    ("Indianapolis", "IN"), ("Seattle", "WA"), ("Denver", "CO"), ("Boston", "MA")
]

PRODUCT_CATEGORIES = ["Electronics", "Clothing", "Home & Garden", "Sports", "Books", "Toys"]

PRODUCTS = [
    # Electronics
    ("Wireless Headphones", "Electronics", 79.99),
    ("Bluetooth Speaker", "Electronics", 49.99),
    ("USB-C Charging Cable", "Electronics", 12.99),
    ("Laptop Stand", "Electronics", 34.99),
    ("Webcam HD 1080p", "Electronics", 59.99),
    ("Mechanical Keyboard", "Electronics", 89.99),
    ("Wireless Mouse", "Electronics", 29.99),
    ("External SSD 500GB", "Electronics", 79.99),
    ("Smart Watch", "Electronics", 199.99),
    ("Portable Charger", "Electronics", 24.99),
    # Clothing
    ("Cotton T-Shirt", "Clothing", 19.99),
    ("Denim Jeans", "Clothing", 49.99),
    ("Running Shoes", "Clothing", 89.99),
    ("Winter Jacket", "Clothing", 129.99),
    ("Wool Sweater", "Clothing", 59.99),
    ("Casual Sneakers", "Clothing", 69.99),
    ("Formal Shirt", "Clothing", 39.99),
    ("Sports Shorts", "Clothing", 24.99),
    # Home & Garden
    ("LED Desk Lamp", "Home & Garden", 29.99),
    ("Coffee Maker", "Home & Garden", 79.99),
    ("Plant Pot Set", "Home & Garden", 19.99),
    ("Throw Blanket", "Home & Garden", 34.99),
    ("Kitchen Scale", "Home & Garden", 24.99),
    ("Air Purifier", "Home & Garden", 149.99),
    ("Vacuum Cleaner", "Home & Garden", 199.99),
    ("Toaster", "Home & Garden", 39.99),
    # Sports
    ("Yoga Mat", "Sports", 29.99),
    ("Resistance Bands", "Sports", 14.99),
    ("Water Bottle", "Sports", 19.99),
    ("Fitness Tracker", "Sports", 49.99),
    ("Dumbbell Set", "Sports", 89.99),
    ("Jump Rope", "Sports", 9.99),
    ("Tennis Racket", "Sports", 79.99),
    ("Soccer Ball", "Sports", 24.99),
    # Books
    ("Python Programming", "Books", 39.99),
    ("Machine Learning Basics", "Books", 49.99),
    ("Data Science Handbook", "Books", 44.99),
    ("Clean Code", "Books", 34.99),
    ("Design Patterns", "Books", 54.99),
    ("The Pragmatic Programmer", "Books", 49.99),
    # Toys
    ("Building Blocks Set", "Toys", 29.99),
    ("Remote Control Car", "Toys", 39.99),
    ("Board Game Collection", "Toys", 24.99),
    ("Puzzle 1000 Pieces", "Toys", 14.99),
    ("Action Figure", "Toys", 19.99),
    ("Plush Toy", "Toys", 12.99),
    ("Art Supply Kit", "Toys", 34.99),
    ("Science Kit", "Toys", 44.99),
    ("Card Game", "Toys", 9.99),
    ("Educational Robot", "Toys", 79.99),
]

ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]


def create_tables(conn: sqlite3.Connection):
    """Create all tables."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock_quantity INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            total_amount REAL NOT NULL,
            created_at TIMESTAMP NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    conn.commit()


def populate_customers(conn: sqlite3.Connection, count: int = 50):
    """Populate customers table."""
    cursor = conn.cursor()

    used_emails = set()
    for _ in range(count):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)

        # Generate unique email
        base_email = f"{first_name.lower()}.{last_name.lower()}"
        email = f"{base_email}@email.com"
        counter = 1
        while email in used_emails:
            email = f"{base_email}{counter}@email.com"
            counter += 1
        used_emails.add(email)

        city, state = random.choice(CITIES)

        cursor.execute(
            "INSERT INTO customers (first_name, last_name, email, city, state) VALUES (?, ?, ?, ?, ?)",
            (first_name, last_name, email, city, state)
        )

    conn.commit()


def populate_products(conn: sqlite3.Connection):
    """Populate products table."""
    cursor = conn.cursor()

    for name, category, price in PRODUCTS:
        stock = random.randint(10, 200)
        cursor.execute(
            "INSERT INTO products (name, category, price, stock_quantity) VALUES (?, ?, ?, ?)",
            (name, category, price, stock)
        )

    conn.commit()


def populate_orders(conn: sqlite3.Connection, count: int = 100):
    """Populate orders and order_items tables."""
    cursor = conn.cursor()

    # Get customer and product IDs
    cursor.execute("SELECT id FROM customers")
    customer_ids = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT id, price FROM products")
    products = [(row[0], row[1]) for row in cursor.fetchall()]

    # Generate orders over the past year
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    for _ in range(count):
        customer_id = random.choice(customer_ids)

        # Random date in the past year
        days_ago = random.randint(0, 365)
        order_date = end_date - timedelta(days=days_ago)

        # Status based on order age
        if days_ago < 3:
            status = random.choice(["pending", "processing"])
        elif days_ago < 14:
            status = random.choice(["processing", "shipped", "delivered"])
        else:
            status = random.choice(["delivered", "delivered", "delivered", "cancelled"])

        # Create order with placeholder total
        cursor.execute(
            "INSERT INTO orders (customer_id, status, total_amount, created_at) VALUES (?, ?, ?, ?)",
            (customer_id, status, 0, order_date.isoformat())
        )
        order_id = cursor.lastrowid

        # Add 1-5 items to the order
        num_items = random.randint(1, 5)
        order_total = 0

        selected_products = random.sample(products, min(num_items, len(products)))
        for product_id, unit_price in selected_products:
            quantity = random.randint(1, 3)
            item_total = unit_price * quantity
            order_total += item_total

            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (order_id, product_id, quantity, unit_price)
            )

        # Update order total
        cursor.execute(
            "UPDATE orders SET total_amount = ? WHERE id = ?",
            (round(order_total, 2), order_id)
        )

    conn.commit()


def setup_database():
    """Set up the complete database."""
    # Remove existing database
    if DB_PATH.exists():
        DB_PATH.unlink()

    # Create and populate
    conn = sqlite3.connect(DB_PATH)

    print("Creating tables...")
    create_tables(conn)

    print("Populating customers...")
    populate_customers(conn, count=50)

    print("Populating products...")
    populate_products(conn)

    print("Populating orders...")
    populate_orders(conn, count=100)

    # Print summary
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM customers")
    print(f"  - Customers: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM products")
    print(f"  - Products: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM orders")
    print(f"  - Orders: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM order_items")
    print(f"  - Order items: {cursor.fetchone()[0]}")

    conn.close()
    print(f"\nDatabase created at: {DB_PATH}")


if __name__ == "__main__":
    setup_database()
