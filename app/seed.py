import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Business
from app.auth import hash_password

DATABASE_URL = "postgresql://don:jqh40ybn6P%21@localhost:5432/ragproject"
engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def seed():
    # Create all tables + any missing columns
    Base.metadata.create_all(bind=engine)

    # Add hashed_password column if it doesn't exist yet
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS hashed_password VARCHAR NOT NULL DEFAULT '';
        """))
        conn.execute(text("""
            ALTER TABLE users
            ALTER COLUMN hashed_password DROP DEFAULT;
        """))
        conn.commit()

    db = SessionLocal()
    try:
        # Create business
        business = db.query(Business).filter(Business.name == "Acme Inc").first()
        if not business:
            business = Business(name="Acme Inc")
            db.add(business)
            db.flush()
            print("  Created business: Acme Inc")
        else:
            print("  Business already exists, skipping.")

        # Create user
        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            user = User(
                email           = "test@example.com",
                name            = "Test User",
                hashed_password = hash_password("testpass123"),
            )
            db.add(user)
            db.flush()
            print("  Created user: test@example.com")
        else:
            user.hashed_password = hash_password("testpass123")
            print("  User already exists, password reset for local dev.")

        # Link user to business
        if business not in user.businesses:
            user.businesses.append(business)
            print("  Linked user to business.")

        db.commit()
        print("\nSeed complete.")
        print("\nTest credentials:")
        print("  Email:    test@example.com")
        print("  Password: testpass123")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()