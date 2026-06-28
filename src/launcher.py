import os
import sys
import dotenv
import uvicorn

dotenv.load_dotenv()

if not os.environ.get("CONFIG_DIR"):
    from src.directory_picker import pick_directory
    pick_directory()
    dotenv.load_dotenv()

if not os.environ.get("CONFIG_DIR"):
    sys.exit("No config directory selected.")

uvicorn.run("src.api:app", host="127.0.0.1", port=8000)
