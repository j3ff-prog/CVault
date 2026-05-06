"""
database.py
SQLite connection and schema.
"""
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "cvault.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name      TEXT    NOT NULL,
            last_name       TEXT    NOT NULL,
            email           TEXT    NOT NULL UNIQUE,
            phone           TEXT    NOT NULL,
            password_hash   TEXT    NOT NULL,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            is_active       INTEGER NOT NULL DEFAULT 1
        )
    """)

    # CREDITS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS credits (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL UNIQUE REFERENCES users(id),
            single_credits    INTEGER NOT NULL DEFAULT 0,
            triple_credits    INTEGER NOT NULL DEFAULT 0,
            unlimited_until   TEXT    DEFAULT NULL
        )
    """)

    # PAYMENTS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            paystack_ref    TEXT    NOT NULL UNIQUE,
            plan_type       TEXT    NOT NULL,
            amount_kes      INTEGER NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'pending',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            verified_at     TEXT    DEFAULT NULL
        )
    """)

    # APPLICATIONS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL REFERENCES users(id),
            job_title        TEXT    NOT NULL,
            company          TEXT    DEFAULT '',
            match_score      INTEGER DEFAULT NULL,
            matched_keywords TEXT    DEFAULT '[]',
            generated_cv     TEXT    DEFAULT NULL,
            generated_cl     TEXT    DEFAULT NULL,
            created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # PASSWORD RESET TOKENS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            token       TEXT    NOT NULL UNIQUE,
            expires_at  TEXT    NOT NULL,
            used        INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Tables initialised.")
