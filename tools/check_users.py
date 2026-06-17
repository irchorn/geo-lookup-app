
import sqlite3
import os

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
        print(f"      Created: {user[3]} | Last Login: {user[4]}")
    print("=" * 70)

if __name__ == "__main__":
    list_users()