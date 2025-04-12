from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# Ajustes básicos

def adjust_brightness(image, factor):
    """Adjust the brightness of the image."""
    enhancer = ImageEnhance.Brightness(image)
    return enhancer.enhance(factor)

def adjust_contrast(image, factor):
    """Adjust the contrast of the image."""
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)

def adjust_saturation(image, factor):
    """Adjust the saturation of the image."""
    enhancer = ImageEnhance.Color(image)
    return enhancer.enhance(factor)

def adjust_sharpness(image, factor):
    """Adjust the sharpness of the image."""
    enhancer = ImageEnhance.Sharpness(image)
    return enhancer.enhance(factor)

# Filtros artísticos
def apply_grayscale(image):
    """Convert the image to grayscale."""
    return image.convert("L")

def apply_sepia(image):
    """Apply a sepia filter to the image."""
    sepia_image = image.convert("RGB")
    width, height = sepia_image.size
    pixels = sepia_image.load()  # create the pixel map

    for py in range(height):
        for px in range(width):
            r, g, b = sepia_image.getpixel((px, py))

            tr = int(0.393 * r + 0.769 * g + 0.189 * b)
            tg = int(0.349 * r + 0.686 * g + 0.168 * b)
            tb = int(0.272 * r + 0.534 * g + 0.131 * b)

            if tr > 255:
                tr = 255

            if tg > 255:
                tg = 255

            if tb > 255:
                tb = 255

            pixels[px, py] = (tr, tg, tb)

    return sepia_image

def apply_negative(image):
    """Apply a negative filter to the image."""
    return ImageOps.invert(image.convert("RGB"))

def apply_pixelate(image, pixel_size):
    """Apply a pixelation effect to the image."""
    small = image.resize((image.size[0]//pixel_size, image.size[1]//pixel_size), resample=Image.BILINEAR)
    return small.resize(image.size, Image.NEAREST)

# Efeitos vintage/retro
def apply_vintage(image):
    """Apply a vintage effect to the image."""
    # This is a placeholder for a more complex vintage effect
    return image.filter(ImageFilter.GaussianBlur(2))