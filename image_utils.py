# file: image_utils.py
import os
from tkinter import filedialog
from PIL import Image
from typing import Optional

def load_image_dialog() -> Optional[str]:
    file_path = filedialog.askopenfilename(
        filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif *.ico")]
    )
    return file_path if file_path else None

def save_image_dialog(image: Image.Image) -> Optional[str]:
    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[
            ("PNG", "*.png"),
            ("JPEG", "*.jpg *.jpeg"),
            ("BMP", "*.bmp"),
            ("GIF", "*.gif"),
            ("TIFF", "*.tiff"),
            ("ICO", "*.ico"),
            ("WebP", "*.webp"),
        ]
    )
    if file_path:
        image.save(file_path)
        return file_path
    return None