from app.config import get_settings
from app.db import init_db
from app.seed.run import seed_database

if __name__ == "__main__":
    init_db(get_settings())
    seed_database()
