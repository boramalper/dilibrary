import os
import sqlite3

if os.path.exists("database.sqlite3"):
    exit("'database.sqlite3' exists in the current directory, aborting to prevent data loss.")

db_conn = sqlite3.connect("database.sqlite3")
db_conn.execute("""
    CREATE TABLE "news" (
        "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        "title" TEXT NOT NULL,
        "body" TEXT NOT NULL,
        "created" TEXT NOT NULL,
        "is_deleted" INTEGER NOT NULL DEFAULT (0),
        "uuid" TEXT NOT NULL
    );
    """
                )

db_conn.execute("""
    CREATE TABLE "admins" (
        "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        "username" TEXT NOT NULL,
        "password" TEXT NOT NULL
    );
    """
                )

db_conn.commit()
db_conn.close()

print("'database.sqlite3' created.")
