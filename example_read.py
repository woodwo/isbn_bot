import sqlite3

def save_cover_to_file(book_id, output_file_path, cursor):
    # Assuming 'books' is your table name
    cursor.execute("SELECT cover FROM books WHERE id=?", (book_id,))
    cover_data = cursor.fetchone()

    if cover_data:
        with open(output_file_path, 'wb') as file:
            file.write(cover_data[0])
        print(f"Cover data for book {book_id} saved to {output_file_path}")
    else:
        print(f"No cover data found for book {book_id}")

# Example usage:
# Replace 'your_database.db' with your actual SQLite database file
db_file = 'books.db'
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Replace 1 with the actual book_id and 'output_cover.jpg' with the desired output file path
save_cover_to_file(5, 'output_cover.jpg', cursor)

# Close the connection when done
conn.close()
