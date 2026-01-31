# database.py
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import logging
from datetime import datetime
from config import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """Database connection တည်ဆောက်မယ်"""
        try:
            self.conn = psycopg.connect(config.DATABASE_URL)
            logger.info("✅ Database connection successful")
            self.create_tables()
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            raise
    
    def create_tables(self):
        """လိုအပ်တဲ့ tables တွေ create လုပ်မယ်"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS channel_posts (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL,
                channel_id BIGINT NOT NULL,
                message_type VARCHAR(50),
                content TEXT,
                caption TEXT,
                media_url TEXT,
                file_id TEXT,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                views INTEGER DEFAULT 0,
                date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, channel_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                post_id VARCHAR(255) UNIQUE NOT NULL,
                title TEXT,
                content TEXT,
                link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                level VARCHAR(20),
                message TEXT,
                source VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        try:
            with self.conn.cursor() as cur:
                for table_sql in tables:
                    cur.execute(table_sql)
                self.conn.commit()
                logger.info("✅ Database tables created/verified")
        except Exception as e:
            logger.error(f"❌ Table creation error: {e}")
            self.conn.rollback()
    
    def save_channel_post(self, post_data):
        """Channel post ကို database မှာ save လုပ်မယ်"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO channel_posts 
                    (post_id, channel_id, message_type, content, caption, media_url, 
                     file_id, file_size, width, height, date) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (post_id, channel_id) DO UPDATE
                    SET content = EXCLUDED.content,
                        caption = EXCLUDED.caption,
                        media_url = EXCLUDED.media_url,
                        file_id = EXCLUDED.file_id,
                        file_size = EXCLUDED.file_size,
                        width = EXCLUDED.width,
                        height = EXCLUDED.height,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (
                    post_data.get('message_id'),
                    post_data.get('channel_id'),
                    post_data.get('message_type'),
                    post_data.get('content', ''),
                    post_data.get('caption', ''),
                    post_data.get('media_url'),
                    post_data.get('file_id'),
                    post_data.get('file_size'),
                    post_data.get('width'),
                    post_data.get('height'),
                    datetime.fromtimestamp(post_data.get('date')) if post_data.get('date') else None
                ))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Channel post save error: {e}")
            self.conn.rollback()
            return False
    
    def get_channel_posts(self, limit=50, offset=0):
        """Channel posts အားလုံးကို ယူမယ်"""
        try:
            with self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute("""
                    SELECT * FROM channel_posts 
                    ORDER BY date DESC 
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Get channel posts error: {e}")
            return []
    
    def get_channel_post_by_id(self, post_id):
        """Channel post by ID"""
        try:
            with self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM channel_posts WHERE post_id = %s", (post_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Get channel post error: {e}")
            return None
    
    def get_post_count(self):
        """Total post count"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as count FROM channel_posts")
                return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"❌ Get post count error: {e}")
            return 0
    
    def get_stats(self):
        """Get channel statistics"""
        try:
            with self.conn.cursor() as cur:
                # Total posts
                cur.execute("SELECT COUNT(*) as total_posts FROM channel_posts")
                total_posts = cur.fetchone()[0]
                
                # Posts by type
                cur.execute("""
                    SELECT 
                        message_type,
                        COUNT(*) as count
                    FROM channel_posts
                    GROUP BY message_type
                """)
                type_counts = {row[0]: row[1] for row in cur.fetchall()}
                
                # Latest post date
                cur.execute("SELECT MAX(date) as latest_post FROM channel_posts")
                latest_post = cur.fetchone()[0]
                
                return {
                    'total_posts': total_posts,
                    'type_counts': type_counts,
                    'latest_post': latest_post
                }
        except Exception as e:
            logger.error(f"❌ Get stats error: {e}")
            return {'total_posts': 0, 'type_counts': {}, 'latest_post': None}
    
    def save_post(self, post_id, title, content, link=None):
        """Regular post ကို save လုပ်မယ်"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO posts (post_id, title, content, link) 
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (post_id) DO UPDATE
                    SET title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        link = EXCLUDED.link,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (post_id, title, content, link))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Post save error: {e}")
            self.conn.rollback()
            return False
    
    def get_post(self, post_id):
        """Get a post by ID"""
        try:
            with self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM posts WHERE post_id = %s", (post_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Get post error: {e}")
            return None
    
    def get_all_posts(self, limit=100):
        """Get all posts"""
        try:
            with self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT %s", (limit,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Get all posts error: {e}")
            return []
    
    def add_log(self, level, message, source):
        """Add log entry"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO logs (level, message, source) VALUES (%s, %s, %s)",
                    (level, message, source)
                )
                self.conn.commit()
        except Exception as e:
            logger.error(f"❌ Log save error: {e}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

# Global database instance
db = Database()
