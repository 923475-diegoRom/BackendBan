import os
import uuid
from faker import Faker
from app.supabase_client import supabase, create_user, create_card, create_contact

fake = Faker('es_MX')

def seed_demo_users():
    # Create two demo users with one Banorte card each and three contacts
    for i in range(2):
        name = fake.name()
        user = create_user(name)
        user_id = user["id"] if isinstance(user, dict) else user.get("id")
        create_card(user_id)
        for _ in range(3):
            contact_name = fake.name()
            contact_phone = fake.phone_number()
            create_contact(user_id, contact_name, contact_phone)
        print(f"Created demo user {name} with id {user_id}")

if __name__ == "__main__":
    # Ensure Supabase credentials are loaded from environment
    from dotenv import load_dotenv
    load_dotenv()
    seed_demo_users()
