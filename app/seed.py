from app.database import SessionLocal, engine
from app.models import User, Business, Base

def seed():
    db = SessionLocal()
    try:
        business = db.query(Business).first()
        if not business:
            business = Business(name="Acme Inc")
            db.add(business)
            db.flush()

        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            user = User(email="test@example.com", name="Test User")
            db.add(user)
            db.flush()

        if business not in user.businesses:
            user.businesses.append(business)

        db.commit()

        print("Seeding complete")

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        db.close()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed()