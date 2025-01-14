import sqlite3

DB_PATH = "titles.db"


def init_db():
    """Khởi tạo cơ sở dữ liệu nếu chưa tồn tại."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_titles (
            original_title TEXT PRIMARY KEY,
            translated_title TEXT,
            last_accessed INTEGER
        )
    """
    )
    conn.commit()
    conn.close()


def count_titles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM video_titles")
    count = cursor.fetchone()[0]
    return count


if __name__ == "__main__":
    init_db()
    print(f"Total records in the table: {count_titles()}")
