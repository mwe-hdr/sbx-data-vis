import tkinter as tk

start_x = start_y = 0
rect = None

def on_press(event):
    global start_x, start_y, rect
    start_x = event.x_root
    start_y = event.y_root

def on_drag(event):
    global rect

    canvas.delete("selection")

    x1 = start_x
    y1 = start_y
    x2 = event.x_root
    y2 = event.y_root

    canvas.create_rectangle(
        x1, y1, x2, y2,
        outline="red",
        width=2,
        tags="selection"
    )

def on_release(event):
    x1 = min(start_x, event.x_root)
    y1 = min(start_y, event.y_root)
    x2 = max(start_x, event.x_root)
    y2 = max(start_y, event.y_root)

    print("\nCoordinates:")
    print(f"x = {x1}")
    print(f"y = {y1}")
    print(f"width  = {x2 - x1}")
    print(f"height = {y2 - y1}")

    root.destroy()

root = tk.Tk()
root.attributes("-fullscreen", True)
root.attributes("-alpha", 0.25)
root.configure(bg="gray")

canvas = tk.Canvas(root)
canvas.pack(fill="both", expand=True)

root.bind("<ButtonPress-1>", on_press)
root.bind("<B1-Motion>", on_drag)
root.bind("<ButtonRelease-1>", on_release)

root.mainloop()