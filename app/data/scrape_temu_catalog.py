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

# Verified high-res Unsplash photo IDs for diverse physical product photography
UNSPLASH_PHOTO_POOL = [
    "1522335789203-aabd1fc54bc9", "1526170375885-4d8ecf77b99f", "1542291026-7eec264c27ff",
    "1505740420928-5e560c06d30e", "1583394838336-acd977736f90", "1572635196237-14b3f281503f",
    "1546868871-7041f2a55e12", "1584917865442-de89df76afd3", "1608231387042-66d1773070a5",
    "1585386959984-a4155224a1ad", "1593998066526-65fcabfb0b7e", "1560343090-f0409e92791a",
    "1523275335684-37898b6baf30", "1503602642458-232111445657", "1586495777744-4413f21062fa",
    "1567401893414-76b7b1e5a7a5", "1616486338812-3dadae4b4ace", "1512496015851-a90fb38ba796",
    "1598033129183-c4f50c736f1d", "1517841905240-472988babdf9", "1511556532299-8f662fc26c06"
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def generate_temu_product(category: str, index: int) -> dict:
    """Generate a single Temu product with multiple high-res product photos."""
    clean_cat = category.replace("'", "").replace(",", "").replace(" ", "-").lower()

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

    # Multi-image generation: 4 distinct image URLs per product
    images = []
    for img_idx in range(1, 5):
        photo_id = UNSPLASH_PHOTO_POOL[(index * 7 + img_idx * 3) % len(UNSPLASH_PHOTO_POOL)]
        img_url = f"https://images.unsplash.com/photo-{photo_id}?w=600&auto=format&fit=crop&sig={index}_{img_idx}"
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
