
import sqlite3
import os
from werkzeug.security import generate_password_hash

# Database path (relative to tools folder)
DATABASE = os.path.join(os.path.dirname(__file__), '..', 'instance', 'users.db')

def list_users():
    """List all registered users."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, created_at, last_login FROM users")
    users = cursor.fetchall()
    conn.close()
    
    print("\n" + "=" * 70)
    print("  Registered Users")
    print("=" * 70)
    
    if not users:
        print("  No users registered.")
        return
    
    for user in users:
        print(f"  ID: {user[0]} | Username: {user[1]} | Email: {user[2]}")
    print("=" * 70)

def reset_password():
    """Reset a user's password."""
    email = input("\nEnter user's email: ").strip()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        print(f"No user found with email: {email}")
        conn.close()
        return
    
    new_password = input("Enter new password: ").strip()
    
    if len(new_password) < 6:
        print("Password must be at least 6 characters.")
        conn.close()
        return
    
    password_hash = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", 
                   (password_hash, email))
    conn.commit()
    conn.close()
    
    print(f"\n✓ Password reset for {user[1]} ({email})")
    print(f"  New password: {new_password}")

def delete_user():
    """Delete a user account."""
    email = input("\nEnter user's email to delete: ").strip()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        print(f"No user found with email: {email}")
        conn.close()
        return
    
    confirm = input(f"Delete user '{user[1]}'? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        cursor.execute("DELETE FROM users WHERE email = ?", (email,))
        conn.commit()
        print(f"✓ User '{user[1]}' deleted.")
    else:
        print("Cancelled.")
    
    conn.close()

def main():
    while True:
        print("\n" + "=" * 40)
        print("  NTA App - Admin Tool")
        print("=" * 40)
        print("  1. List all users")
        print("  2. Reset user password")
        print("  3. Delete user")
        print("  4. Exit")
        print("=" * 40)
        
        choice = input("Select option (1-4): ").strip()
        
        if choice == '1':
            list_users()
        elif choice == '2':
            reset_password()
        elif choice == '3':
            delete_user()
        elif choice == '4':
            print("Goodbye!")
            break
        else:
            print("Invalid option.")

if __name__ == "__main__":
    main()