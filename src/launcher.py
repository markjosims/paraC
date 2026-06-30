import os
import sys
import dotenv
import uvicorn

dotenv.load_dotenv()

if not os.environ.get("YAML_DIR"):
    from tkinter import filedialog, Tk

    def pick_directory():
        root = Tk()
        root.withdraw()
        folder_selected = filedialog.askdirectory()
        with open(".env", "w") as f:
            f.write(f"YAML_DIR={folder_selected}")

    pick_directory()
    dotenv.load_dotenv()

if not os.environ.get("YAML_DIR"):
    sys.exit("No config directory selected.")

YAML_DIR = os.environ.get("YAML_DIR")

if __name__ == "__main__":
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True)
