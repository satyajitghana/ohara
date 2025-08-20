"""Script to create a user."""
import sys
import argparse
from sqlmodel import Session

from ..database import engine, create_db_and_tables
from ..auth import create_user


def main():
    """Create a user from command line arguments."""
    parser = argparse.ArgumentParser(description="Create a user")
    parser.add_argument("username", help="Username")
    parser.add_argument("password", help="Password")
    parser.add_argument("email", nargs="?", help="Email address")
    parser.add_argument("full_name", nargs="?", help="Full name")
    
    args = parser.parse_args()
    
    # Set default email if not provided
    if not args.email:
        args.email = f"{args.username}@example.com"
    
    # Create database tables if they don't exist
    create_db_and_tables()
    
    # Create user
    with Session(engine) as session:
        try:
            user = create_user(
                session=session,
                username=args.username,
                email=args.email,
                password=args.password,
                full_name=args.full_name
            )
            print(f"✅ User created successfully!")
            print(f"   Username: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Full Name: {user.full_name or 'Not provided'}")
            print(f"   Created: {user.created_at}")
            
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
