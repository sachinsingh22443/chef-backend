from getpass import getpass

from app.db.session import SessionLocal

# IMPORTANT:
# Load related SQLAlchemy models before querying User
from app.models.refresh_token import RefreshToken
from app.models.user import User

from app.utils.hashing import hash_password


def create_or_reset_admin():
    db = SessionLocal()

    try:
        print("\n================================")
        print("      CREATE / RESET ADMIN")
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

        # =========================================
        # EXISTING USER
        # =========================================

        if existing_user:

            # -------------------------------------
            # EXISTING ADMIN
            # -------------------------------------

            if existing_user.role == "admin":

                print("\n⚠️ Admin account already exists.")
                print("Updating admin password...\n")

                existing_user.name = name
                existing_user.phone = phone or None

                # IMPORTANT:
                # Generate a completely new Argon2id hash
                existing_user.password = hash_password(password)

                existing_user.role = "admin"
                existing_user.is_active = True
                existing_user.is_verified = True
                existing_user.application_status = "approved"

                db.commit()
                db.refresh(existing_user)

                print("================================")
                print("✅ ADMIN PASSWORD RESET SUCCESS")
                print("================================")
                print(f"Name : {existing_user.name}")
                print(f"Email: {existing_user.email}")
                print(f"Role : {existing_user.role}")
                print(f"ID   : {existing_user.id}")
                print("================================\n")

                return

            # -------------------------------------
            # EMAIL BELONGS TO NON-ADMIN
            # -------------------------------------

            print(
                f"❌ This email already belongs to "
                f"a {existing_user.role} account."
            )

            return

        # =========================================
        # CREATE NEW ADMIN
        # =========================================

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
    create_or_reset_admin()