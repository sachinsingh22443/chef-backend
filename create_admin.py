from getpass import getpass

from app.db.session import SessionLocal

# IMPORTANT:
# Load related SQLAlchemy models before querying User
from app.models.refresh_token import RefreshToken
from app.models.user import User

from app.utils.hashing import hash_password


def create_admin():
    db = SessionLocal()

    try:
        print("\n================================")
        print("      CREATE ADMIN ACCOUNT")
        print("================================\n")

        name = input("Admin name: ").strip()
        email = input("Admin email: ").strip().lower()
        phone = input("Admin phone: ").strip()

        password = getpass("Admin password: ")
        confirm_password = getpass("Confirm password: ")

        # -----------------------------------------
        # VALIDATION
        # -----------------------------------------

        if not name:
            print("❌ Name is required")
            return

        if not email:
            print("❌ Email is required")
            return

        if len(password) < 6:
            print("❌ Password must be at least 6 characters")
            return

        if password != confirm_password:
            print("❌ Passwords do not match")
            return

        # -----------------------------------------
        # CHECK EXISTING EMAIL
        # -----------------------------------------

        existing_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing_user:

            if existing_user.role == "admin":
                print("❌ Admin account already exists")
                return

            print(
                f"❌ This email already belongs to "
                f"a {existing_user.role} account."
            )
            return

        # -----------------------------------------
        # CREATE ADMIN
        # -----------------------------------------

        admin = User(
            name=name,
            email=email,
            phone=phone or None,
            password=hash_password(password),
            role="admin",
            is_active=True,
            is_verified=True,
            application_status="approved",
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("\n================================")
        print("✅ ADMIN CREATED SUCCESSFULLY")
        print("================================")
        print(f"Name : {admin.name}")
        print(f"Email: {admin.email}")
        print(f"Role : {admin.role}")
        print(f"ID   : {admin.id}")
        print("================================\n")

    except Exception as e:
        db.rollback()
        print("\n❌ ERROR:", str(e))

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()