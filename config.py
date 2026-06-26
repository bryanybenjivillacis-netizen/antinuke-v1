import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("893295635837644810", "1"))
DATABASE_URL = os.getenv("postgresql://postgres:NgqYVwVzSTQeWudBmPoWaCKGFhEfLbBn@postgres.railway.internal:5432/railway")
PREFIX = os.getenv("PREFIX", ".")
