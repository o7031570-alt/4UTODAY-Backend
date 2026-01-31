# database.py
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import logging
from config import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """Database connection တည်ဆောက်မယ်"""
        try:
            # psycopg3 နဲ့ connect (sslmode='require' ကို connection string ထဲမှာ ထည့်ပါ)
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
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                post_id VARCHAR(255) UNIQUE NOT NULL,
                title TEXT,
                content TEXT,
                link TEXT,
                channel_id VARCHAR(100),
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
    
    def save_post(self, post_id, title, content, link=None, channel_id=None):
        """Post ကို database မှာ save လုပ်မယ်"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO posts (post_id, title, content, link, channel_id) 
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (post_id) DO UPDATE
                    SET title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        link = EXCLUDED.link,
                        channel_id = EXCLUDED.channel_id,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (post_id, title, content, link, channel_id))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Post save error: {e}")
            self.conn.rollback()
            return False
    
    def get_post(self, post_id):
        """Post တစ်ခုကို ရှာမယ်"""
        try:
            with self.conn.cursor(row_factory=dict_row) as cur:  # dict_row ကို သုံးပါ
                cur.execute("SELECT * FROM posts WHERE post_id = %s", (post_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Get post error: {e}")
            return None
    
    def get_all_posts(self, limit=100):
        """Post အားလုံးကို ယူမယ်"""
        try:
            with self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT %s", (limit,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Get all posts error: {e}")
            return []
    
    # ကျန်တဲ့ functions တွေကိုလည်း အလားတူ ပြင်ပါ
    # ...
    
    def close(self):
        """Database connection ကို ပိတ်မယ်"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

# Global database instance
db = Database()
