import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("893295635837644810", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
PREFIX = os.getenv("PREFIX", ".")
