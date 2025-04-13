from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageChops
import numpy as np
from scipy import ndimage

# Tenta importar cv2 para operações avançadas
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

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

# Filtros de suavização e realce
def apply_smooth(image, intensity=1.0):
    """Apply a smoothing filter to the image with adjustable intensity.
    
    Args:
        image: PIL Image object
        intensity: Float between 0.0 and 3.0 controlling the smoothing strength
    
    Returns:
        Smoothed PIL Image
    """
    # Limita a intensidade entre 0.1 e 3.0
    intensity = max(0.1, min(3.0, intensity))
    
    # Converte para modo RGB se necessário
    if image.mode != "RGB":
        image = image.convert("RGB")
    
    # Aplica filtro de suavização com intensidade ajustável
    if CV2_AVAILABLE:
        # Usa OpenCV para suavização mais avançada
        img_array = np.array(image)
        # Calcula o tamanho do kernel baseado na intensidade
        kernel_size = int(intensity * 5)
        # Garante que o kernel seja ímpar
        if kernel_size % 2 == 0:
            kernel_size += 1
        # Aplica filtro bilateral que preserva bordas
        smooth_array = cv2.bilateralFilter(img_array, kernel_size, 
                                          intensity * 75, intensity * 75)
        return Image.fromarray(smooth_array)
    else:
        # Usa filtros nativos do PIL
        # Combina GaussianBlur com MedianFilter para melhor resultado
        blurred = image.filter(ImageFilter.GaussianBlur(radius=intensity))
        if intensity > 1.5:
            # Para intensidades maiores, adiciona filtro de mediana
            median_size = int(intensity * 2)
            if median_size % 2 == 0:
                median_size += 1
            blurred = blurred.filter(ImageFilter.MedianFilter(size=median_size))
        return blurred

def apply_enhance(image, intensity=1.0):
    """Apply an enhancement filter to the image with adjustable intensity.
    This filter enhances the overall vividness of colors and details in the image,
    similar to but distinct from saturation adjustment. While saturation affects
    color intensity directly, this filter combines contrast, sharpness and edge
    enhancement for a more vibrant look.
    
    Args:
        image: PIL Image object
        intensity: Float between 0.0 and 2.0 controlling the enhancement strength
    
    Returns:
        Enhanced PIL Image with improved color vividness
    """
    # Limita a intensidade entre 0.1 e 2.0
    intensity = max(0.1, min(2.0, intensity))
    
    # Converte para modo RGB se necessário
    if image.mode != "RGB":
        image = image.convert("RGB")
    
    # Aplica uma combinação de filtros para realçar a imagem
    if CV2_AVAILABLE:
        # Usa OpenCV para realce mais avançado
        img_array = np.array(image)
        
        # Converte para LAB para separar luminância de cor
        lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        
        # Aplica CLAHE (Contrast Limited Adaptive Histogram Equalization) no canal L
        clahe = cv2.createCLAHE(clipLimit=intensity*2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        
        # Merge dos canais
        enhanced_lab = cv2.merge((cl, a, b))
        
        # Converte de volta para RGB
        enhanced_array = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
        
        # Aplica um pouco de nitidez
        kernel = np.array([[-1, -1, -1],
                          [-1, 9 + intensity, -1],
                          [-1, -1, -1]])
        enhanced_array = cv2.filter2D(enhanced_array, -1, kernel * intensity)
        
        return Image.fromarray(enhanced_array)
    else:
        # Usa filtros nativos do PIL
        # Aumenta contraste
        enhanced = ImageEnhance.Contrast(image).enhance(1.0 + (intensity * 0.3))
        
        # Aumenta nitidez
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.0 + intensity)
        
        # Aplica um filtro de realce de bordas
        if intensity > 0.5:
            edge_enhanced = enhanced.filter(ImageFilter.EDGE_ENHANCE)
            # Mistura a imagem original com a realçada
            blend_factor = min(intensity / 2.0, 0.7)  # Limita o fator de mistura
            enhanced = Image.blend(enhanced, edge_enhanced, blend_factor)
        
        return enhanced