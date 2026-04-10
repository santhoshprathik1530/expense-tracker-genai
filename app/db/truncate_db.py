"""Truncate (clear) all expenses from the database"""
from app.db.client import get_connection

def truncate_expenses():
    """Delete all expenses from the database"""
    confirm = input("⚠️  Are you sure you want to DELETE ALL expenses? (yes/no): ")
    
    if confirm.lower() != "yes":
        print("❌ Cancelled. No data was deleted.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM expenses")
        count = cursor.fetchone()[0]
        
        cursor.execute("DELETE FROM expenses")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'expenses'")
        conn.commit()
        
        print(f"✅ Successfully deleted {count} expense(s)")
        print("✅ Database is now empty")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to truncate database: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    truncate_expenses()
