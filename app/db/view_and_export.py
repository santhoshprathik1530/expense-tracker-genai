"""View and export expenses database to CSV/Excel"""
from app.db.client import get_connection
import csv
import os
from datetime import datetime

def view_database(limit=None):
    """View all expenses in the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        query = """
            SELECT id, user_id, date, description, category, sub_category, amount, currency, created_at
            FROM expenses
            ORDER BY date DESC, created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("📭 Database is empty. No expenses found.")
            return []
        
        print(f"\n📊 Found {len(rows)} expense(s):\n")
        print(f"{'ID':<6} {'User ID':<12} {'Date':<12} {'Category':<15} {'Sub-Cat':<15} {'Amount':<10} {'Currency':<8} {'Description':<40}")
        print("=" * 140)
        
        expenses = []
        for row in rows:
            expenses.append({
                'id': row[0],
                'user_id': row[1],
                'date': row[2],
                'description': row[3],
                'category': row[4],
                'sub_category': row[5],
                'amount': float(row[6]),
                'currency': row[7],
                'created_at': row[8]
            })
            
            desc = (row[3][:37] + '...') if len(row[3]) > 40 else row[3]
            print(f"{row[0]:<6} {row[1]:<12} {str(row[2]):<12} {row[4] or '—':<15} {row[5] or '—':<15} {float(row[6]):<10.2f} {row[7]:<8} {desc:<40}")
        
        return expenses
        
    except Exception as e:
        print(f"❌ Failed to view database: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def export_to_csv(filename="database_export.csv"):
    """Export all expenses to CSV file"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, user_id, date, description, category, sub_category, amount, currency, created_at, updated_at
            FROM expenses
            ORDER BY date DESC, created_at DESC
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            print("📭 Database is empty. Nothing to export.")
            return None
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"expenses_export_{timestamp}.csv"
        
        # Ensure .csv extension
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        # Get the db folder path
        db_folder = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(db_folder, filename)
        
        # Write to CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'ID', 'User ID', 'Date', 'Description', 'Category', 
                'Sub-Category', 'Amount', 'Currency', 'Created At', 'Updated At'
            ])
            
            # Write data
            for row in rows:
                writer.writerow(tuple(row))
        
        print(f"✅ Exported {len(rows)} expense(s) to: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Failed to export to CSV: {e}")
        return None
    finally:
        cursor.close()
        conn.close()



def show_statistics():
    """Show database statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Total expenses
        cursor.execute("SELECT COUNT(*), SUM(amount) FROM expenses")
        count, total = cursor.fetchone()
        
        print(f"\n📈 Database Statistics:")
        print(f"   Total Expenses: {count or 0}")
        print(f"   Total Amount: ${float(total or 0):.2f}")
        
        # By category
        cursor.execute("""
            SELECT category, COUNT(*), SUM(amount)
            FROM expenses
            GROUP BY category
            ORDER BY SUM(amount) DESC
        """)
        
        category_stats = cursor.fetchall()
        if category_stats:
            print(f"\n   By Category:")
            for cat, cnt, amt in category_stats:
                print(f"      {cat or 'Uncategorized':<20} {cnt:>4} expenses  ${float(amt):>10.2f}")
        
        # By currency
        cursor.execute("""
            SELECT currency, COUNT(*), SUM(amount)
            FROM expenses
            GROUP BY currency
            ORDER BY COUNT(*) DESC
        """)
        
        currency_stats = cursor.fetchall()
        if currency_stats:
            print(f"\n   By Currency:")
            for curr, cnt, amt in currency_stats:
                print(f"      {curr:<5} {cnt:>4} expenses  {float(amt):>10.2f}")
        
    except Exception as e:
        print(f"❌ Failed to get statistics: {e}")
    finally:
        cursor.close()
        conn.close()


def main():
    """Interactive menu"""
    while True:
        print("\n" + "="*60)
        print("📊 EXPENSE DATABASE VIEWER")
        print("="*60)
        print("\n1. View all expenses")
        print("2. View recent expenses (last 20)")
        print("3. Show statistics")
        print("4. Export to CSV")
        print("5. Export to Excel")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == "1":
            view_database()
        elif choice == "2":
            view_database(limit=20)
        elif choice == "3":
            show_statistics()
        elif choice == "4":
            export_to_csv()
        elif choice == "5":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")


if __name__ == "__main__":
    main()
