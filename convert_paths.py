import sqlite3
from beets.util import bytestring_path, normpath

# Path to your Beets SQLite database
database_path = 'F:/PROGRAMMING/beets - fork/beets.db'

# Function to convert string paths to bytestring paths
def convert_path_to_blob(path):
    # Normalize and convert the path to a bytestring path
    return normpath(bytestring_path(path))

# Connect to the SQLite database
conn = sqlite3.connect(database_path)
cursor = conn.cursor()

# Query to select all paths (assuming the paths are stored in a column named 'path')
cursor.execute("SELECT id, path FROM items")

# Iterate over all rows and update the paths
for row in cursor.fetchall():
    item_id, path = row
    if path:
        # Convert the path to a bytestring path
        blob_path = convert_path_to_blob(path)
        
        # Update the path in the database
        cursor.execute("UPDATE items SET path = ? WHERE id = ?", (blob_path, item_id))

# Commit the changes and close the connection
conn.commit()
conn.close()

print("Paths have been successfully converted to the Beets-compatible format.")