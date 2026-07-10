import pyautogui
from PIL import Image

# -----------------------
# Capture region
# -----------------------

X = 260
Y = 180
WIDTH = 1600
HEIGHT = 720


# -----------------------
# Output file
# -----------------------
OUTPUT_FILE = r"C:\lwf\sbx-data-vis\capture.png"

image = pyautogui.screenshot(
    region=(X, Y, WIDTH, HEIGHT)
)

image.save(OUTPUT_FILE)

print(f"Saved: {OUTPUT_FILE}")