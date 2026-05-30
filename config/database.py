from larajango.config import env

CONNECTION = env("DB_CONNECTION", "sqlite")
DATABASE = env("DB_DATABASE", "database/database.sqlite3")
