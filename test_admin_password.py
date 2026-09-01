from getpass import getpass

from app.db.session import SessionLocal

# IMPORTANT:
# Load relationship model before User
from app.models.refresh_token import RefreshToken
from app.models.user import User

from app.utils.hashing import verify_password


EMAIL = "sachinsingh22443@gmail.com"


db = SessionLocal()

try:
    user = (
        db.query(User)
        .filter(User.email == EMAIL)
        .first()
    )

    if not user:
        print("❌ ADMIN USER NOT FOUND")
    else:
        print("USER:", user.email)
        print("ROLE:", user.role)
        print("ACTIVE:", user.is_active)
        print("HASH PREFIX:", user.password[:10])
        print("HASH LENGTH:", len(user.password))

        password = getpass("Enter the admin password to test: ")

        result = verify_password(
            password,
            user.password,
        )

        print("PASSWORD MATCH:", result)

finally:
    db.close()