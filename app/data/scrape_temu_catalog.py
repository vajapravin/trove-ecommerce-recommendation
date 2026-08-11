"""Scrape / Generate 3,400+ Temu-style e-commerce products across 34 categories with multi-image support.

Deactivates all previous catalog items (`is_active = False`) and seeds 100+ new active products
per category, each featuring 4 distinct high-resolution product photos (`images_json`).
"""
from __future__ import annotations

import json
import os
import random
import re
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database import SessionLocal, engine
from app.models import Product, Base
from app.services import dual_write
from sqlalchemy import text


TEMU_CATEGORIES = [
    "Recommended",
    "Beauty Personal Care",
    "Women's Clothing",
    "Home Kitchen",
    "Men's Clothing",
    "Women's Shoes",
    "Men's Underwear Sleepwear",
    "Sports Outdoors",
    "Office School Supplies",
    "Toys Games",
    "Kids' Fashion",
    "Electronics",
    "Business, Industry Science",
    "Pet Supplies",
    "Jewellery Accessories",
    "Automotive",
    "Women's Curve Clothing",
    "Musical Instruments",
    "Bags Luggage",
    "Health Household",
    "Patio, Lawn Garden",
    "Tools Home Improvement",
    "Appliances",
    "Women's Lingerie Lounge",
    "Baby Maternity",
    "Men's Big Tall",
    "Smart Home",
    "Arts, Crafts Sewing",
    "Men's Shoes",
    "Kids' Shoes",
    "Mobile Phones Accessories",
    "Food Grocery",
    "Books Media",
    "Beachwear",
    "Furniture",
]

# Verified high-res Unsplash photo IDs mapped to product domain categories
CATEGORY_PHOTO_POOLS = {
    "Beauty Personal Care": ["1522335789203-aabd1fc54bc9", "1598440947619-2c35fc9aa908", "1571781926291-c477ebfd024b", "1556228720-195a672e8a03"],
    "Women's Clothing": ["1515886657613-9f3515b0c78f", "1496747611176-843222e1e57c", "1509631179647-0177331693ae", "1485230895905-ec40ba36b9bc"],
    "Home Kitchen": ["1556911220-e15b29be8c8f", "1584308666744-24d5c474f2ae", "1583847268964-b28dc8f51f92", "1507089947368-19c1da9775ae"],
    "Men's Clothing": ["1617137984095-74e4e5e3613f", "1617137968427-85924c800a22", "1490114538077-0a7f8cb49891", "1507679799987-c73779587ccf"],
    "Women's Shoes": ["1543163521-1bf539c55dd2", "1515347619252-60a4bf4fff4f", "1595950653106-6c9ebd614d3a", "1560343090-f0409e92791a"],
    "Men's Shoes": ["1542291026-7eec264c27ff", "1525966222134-fcfa99b8ae77", "1560769629-975ec94e6a86", "1595950653106-6c9ebd614d3a"],
    "Electronics": ["1505740420928-5e560c06d30e", "1546868871-7041f2a55e12", "1583394838336-acd977736f90", "1572635196237-14b3f281503f"],
    "Sports Outdoors": ["1517838277536-f5f99be501cd", "1584735935682-2f2b69dff9d2", "1571019613454-1cb2f99b2d8b", "1541534741688-6078c6bfb5c5"],
    "Toys Games": ["1566576912321-d58ddd7a6088", "1515488042361-ee00e0ddd4e4", "1596461404969-9ae70f2830c1", "1587654780291-39c9404d746b"],
    "Pet Supplies": ["1543466835-00a7907e9de1", "1583511655857-d19b40a7a54e", "1537151608828-ea2b11777ee8", "1514888286974-6c03e2ca1dba"],
    "Jewellery Accessories": ["1515562141207-7a88fb7ce338", "1535632066927-ab7c9ab60908", "1599643478518-a784e5dc4c8f", "1522335789203-aabd1fc54bc9"],
    "Automotive": ["1511919884226-fd3cad34687c", "1503376780353-7e6692767b70", "1552519507-da3b142c6e3d", "1492144534655-ae79c964c9d7"],
    "Musical Instruments": ["1511671782779-c97d3d27a1d4", "1514525253161-7a46d19cd819", "1520523839897-bd0b52f945a0", "1465847899084-d164df4dedc6"],
    "Bags Luggage": ["1553062407-98eeb64c6a62", "1584917865442-de89df76afd3", "1548036328-c9fa89d128fa", "1608231387042-66d1773070a5"],
    "Food Grocery": ["1540420773420-3366772f4999", "1498837167922-ddd27525d352", "1504674900247-0877df9cc836", "1567620832903-9fc6debc209f"],
    "Furniture": ["1555041469-a586c61ea9bc", "1586023492125-27b2c045efd7", "1616486338812-3dadae4b4ace", "1538688525198-9b88f6f53126"],
    "Tools Home Improvement": ["1504148455328-c376907d081c", "1581092160607-ee22621dd758", "1572981779307-38b8cabb2407", "1530124566582-a618bc2615dc"],
    "Patio, Lawn Garden": ["1585320806297-9794b3e4eeae", "1416879595882-3373a0480b5b", "1516253593875-bd7ba052fbc5", "1501004318641-b39e6451bec6"],
    "Office School Supplies": ["1585386959984-a4155224a1ad", "1513542789411-b6a5d4f31634", "1456513080510-7bf3a84b82f8", "1586075010923-2dd4570fb338"],
    "Mobile Phones Accessories": ["1580910051074-3eb694886505", "1565849904461-04a58ad377e0", "1511707171634-5f897ff02aa9", "1541807084-5c52b6b3adef"]
}
DEFAULT_PHOTO_POOL = ["1505740420928-5e560c06d30e", "1542291026-7eec264c27ff", "1523275335684-37898b6baf30", "1503602642458-232111445657"]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def generate_temu_product(category: str, index: int) -> dict:
    """Generate a single Temu product with multiple high-res product photos."""
    clean_cat = category.replace("'", "").replace(",", "").replace(" ", "-").lower()

    # Select domain photo pool matching category
    photo_pool = CATEGORY_PHOTO_POOLS.get(category) or DEFAULT_PHOTO_POOL

    # Product titles template by category domain
    title_templates = {
        "Beauty Personal Care": [
            "Hydrating Hyaluronic Acid Serum & Facial Roller Set",
            "Waterproof Long-Lasting Liquid Eyeliner Pen",
            "Professional Salon Hair Dryer with Diffuser Attachment",
            "Organic Argan Oil Hair Mask & Repair Treatment",
            "Electric Sonic Facial Cleansing Brush & Massager"
        ],
        "Women's Clothing": [
            "Casual High-Waisted Wide-Leg Linen Trousers",
            "Floral Print Midi Wrap Dress with Puff Sleeves",
            "Oversized Knit Cardigan Sweater with Front Pockets",
            "Seamless Breathable Ribbed Crop Top Tank",
            "Elegant V-Neck Satin Button-Down Blouse"
        ],
        "Home Kitchen": [
            "Non-Stick Granite Frying Pan with Wooden Handle",
            "Automatic Stainless Steel Salt & Pepper Grinder",
            "Aesthetic Ceramic Coffee Mug & Saucer Set",
            "Expandable Bamboo Cutlery Drawer Organizer",
            "Multi-Layer Airtight Food Storage Container Set"
        ],
        "Electronics": [
            "Ultralight Wireless Noise-Canceling Earbuds with LED Case",
            "Portable Bluetooth Speaker with RGB Light Mode",
            "1080P HD Wireless Security Camera with Night Vision",
            "Ergonomic RGB Gaming Mouse with 6 DPI Levels",
            "Fast Wireless Charging Stand for Phone & Watch"
        ],
        "Sports Outdoors": [
            "Insulated Stainless Steel Water Bottle with Straw Lid",
            "Non-Slip Eco-Friendly Yoga Mat with Carrying Strap",
            "Resistance Loop Exercise Bands Set of 5",
            "Ultralight Breathable Running Belt Waist Pack",
            "Adjustable Ankle & Wrist Weights Set"
        ],
        "Mobile Phones Accessories": [
            "Magnetic Magsafe Clear Case for iPhone",
            "3-in-1 Foldable Wireless Charging Station",
            "Privacy Tempered Glass Screen Protector 2-Pack",
            "Universal Adjustable Desktop Phone Stand Holder",
            "Braided Nylon Fast Charging Type-C Cable 6ft"
        ],
        "Furniture": [
            "Modern Minimalist Velvet Accent Chair with Gold Legs",
            "Ergonomic Mesh Office Desk Chair with Lumbar Support",
            "2-Tier Wooden Coffee Table with Storage Shelf",
            "Modular Floating Wall Shelf Unit Set of 3",
            "Foldable Bamboo Shoe Rack Bench Organizer"
        ]
    }

    templates = title_templates.get(category) or [
        f"Premium {category} Essential Unit #{index}",
        f"Smart Modern {category} Multi-Pack #{index}",
        f"Ergonomic High-Performance {category} Set #{index}",
        f"Compact Portable {category} Kit #{index}",
        f"Pro Grade {category} Deluxe #{index}"
    ]

    base_title = templates[(index - 1) % len(templates)]
    variant_suffix = f" (Model {index})" if index > len(templates) else ""
    title = f"{base_title}{variant_suffix}"

    price = round(random.uniform(2.99, 79.99), 2)
    tags = f"{clean_cat},temu,deal,top-rated,fast-shipping"

    # Multi-image generation: 4 domain-matched image URLs per product
    images = []
    for img_idx in range(len(photo_pool)):
        photo_id = photo_pool[(index + img_idx) % len(photo_pool)]
        img_url = f"https://images.unsplash.com/photo-{photo_id}?w=600&auto=format&fit=crop"
        images.append(img_url)

    description = (
        f"High quality {title} designed for modern daily lifestyle. Features premium durable materials, "
        f"stylish design, and top customer ratings. Package includes product unit and user manual. "
        f"Fast Temu logistics delivery guaranteed."
    )


    return {
        "title": title,
        "description": description,
        "category": category,
        "level": "beginner" if index % 3 == 1 else ("intermediate" if index % 3 == 2 else "advanced"),
        "price": price,
        "image_url": images[0],
        "images": images,
        "tags": tags,
        "is_active": True,
    }


def migrate_temu_catalog():
    """Deactivate existing items and seed 100+ items per category across 35 Temu categories."""
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE products ADD COLUMN images_json TEXT;"))
            conn.commit()
            print("Added images_json column to products table.")
        except Exception:
            pass  # column already exists

    db = SessionLocal()
    try:
        print("Deactivating existing catalog products...")
        deactivated = db.query(Product).filter(Product.is_active == True).update({"is_active": False})  # noqa: E712
        db.commit()
        print(f"Deactivated {deactivated} existing products.")


        all_items = []
        item_counter = 1

        print(f"Generating 100 products for each of the {len(TEMU_CATEGORIES)} Temu categories...")
        for cat in TEMU_CATEGORIES:
            for i in range(1, 101):
                item = generate_temu_product(cat, item_counter)
                all_items.append(item)
                item_counter += 1

        total_new = len(all_items)
        print(f"Generated {total_new} total Temu products (~{total_new // len(TEMU_CATEGORIES)} per category).")

        # Bulk create in batches of 500 for optimal performance
        batch_size = 500
        created_count = 0
        for b_idx in range(0, total_new, batch_size):
            batch = all_items[b_idx : b_idx + batch_size]
            dual_write.bulk_create_products(db, batch)
            created_count += len(batch)
            print(f"Seeded batch {b_idx // batch_size + 1}: {created_count}/{total_new} products into SQLite & Chroma...")

        # Update app/starter_catalog.json for fresh boot preloading
        catalog_path = os.path.abspath("app/starter_catalog.json")
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(all_items, f, indent=2)

        print(f"Saved {len(all_items)} items to {catalog_path}.")

        active_count = db.query(Product).filter(Product.is_active == True).count()  # noqa: E712
        print(f"\n✅ Migration Complete! Active products in DB: {active_count}")

    finally:
        db.close()


if __name__ == "__main__":
    migrate_temu_catalog()
