# file: image_processor.py
from PIL import Image, ImageTk
import numpy as np
from typing import Optional, Tuple, Union
import io

class ImageProcessor:
    @staticmethod
    def resize_image(image: Image.Image, width: int, height: int, keep_aspect: bool = True) -> Image.Image:
        """Redimensiona uma imagem para as dimensões especificadas."""
        if keep_aspect:
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
            return image
        return image.resize((width, height), Image.Resampling.LANCZOS)

    @staticmethod
    def rotate_image(image: Image.Image, angle: float, expand: bool = True) -> Image.Image:
        """Rotaciona uma imagem pelo ângulo especificado."""
        return image.rotate(angle, expand=expand, resample=Image.Resampling.BICUBIC)

    @staticmethod
    def create_thumbnail(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
        """Cria uma miniatura da imagem."""
        thumb = image.copy()
        thumb.thumbnail(size, Image.Resampling.LANCZOS)
        return thumb

    @staticmethod
    def convert_to_photoimage(image: Image.Image) -> ImageTk.PhotoImage:
        """Converte uma imagem PIL para PhotoImage do Tkinter."""
        return ImageTk.PhotoImage(image)

    @staticmethod
    def calculate_new_dimensions(image: Image.Image, canvas_width: int, canvas_height: int, 
                               fit_mode: str = "fit") -> Tuple[int, int]:
        """Calcula as novas dimensões baseadas no modo de ajuste."""
        img_width, img_height = image.size
        aspect_ratio = img_width / img_height

        if fit_mode == "width":
            new_width = canvas_width
            new_height = int(canvas_width / aspect_ratio)
        elif fit_mode == "height":
            new_height = canvas_height
            new_width = int(canvas_height * aspect_ratio)
        else:  # fit
            canvas_ratio = canvas_width / canvas_height
            if aspect_ratio > canvas_ratio:
                new_width = canvas_width
                new_height = int(canvas_width / aspect_ratio)
            else:
                new_height = canvas_height
                new_width = int(canvas_height * aspect_ratio)

        return new_width, new_height

    @staticmethod
    def apply_zoom(image: Image.Image, zoom_level: float) -> Image.Image:
        """Aplica zoom à imagem."""
        if zoom_level == 1.0:
            return image
        
        new_width = int(image.width * zoom_level)
        new_height = int(image.height * zoom_level)
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    @staticmethod
    def get_image_info(image: Image.Image) -> dict:
        """Retorna informações sobre a imagem."""
        return {
            "size": image.size,
            "mode": image.mode,
            "format": image.format,
            "info": image.info,
            "is_animated": getattr(image, "is_animated", False),
            "n_frames": getattr(image, "n_frames", 1)
        }

    @staticmethod
    def optimize_memory(image: Image.Image) -> Image.Image:
        """Otimiza o uso de memória da imagem."""
        # Converte para um formato que usa menos memória se possível
        if image.mode in ['RGBA', 'RGBa']:
            return image
        return image.convert('RGB')

    @staticmethod
    def create_blank_image(width: int, height: int, color: str = "white") -> Image.Image:
        """Cria uma imagem em branco com as dimensões especificadas."""
        return Image.new('RGB', (width, height), color)

    @staticmethod
    def get_image_bytes(image: Image.Image, format: str = "PNG") -> bytes:
        """Converte a imagem para bytes."""
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=format)
        return img_byte_arr.getvalue()

    @staticmethod
    def process_pan(current_pos: Tuple[float, float], delta: Tuple[float, float], 
                   canvas_size: Tuple[int, int], image_size: Tuple[int, int], 
                   min_visible: int = 50) -> Tuple[float, float]:
        """
        Processa o movimento de pan da imagem.
        
        Args:
            current_pos: Posição atual da imagem (x, y)
            delta: Deslocamento do mouse (dx, dy)
            canvas_size: Dimensões do canvas (width, height)
            image_size: Dimensões da imagem (width, height)
            min_visible: Pixels mínimos visíveis da imagem
            
        Returns:
            Tuple[float, float]: Nova posição da imagem (x, y)
        """
        # Calcula a nova posição
        new_x = current_pos[0] + delta[0]
        new_y = current_pos[1] + delta[1]
        
        # Obtém as dimensões
        canvas_width, canvas_height = canvas_size
        image_width, image_height = image_size
        
        # Limita o movimento para manter a imagem visível
        new_x = max(min_visible - image_width/2, new_x)
        new_x = min(canvas_width - min_visible + image_width/2, new_x)
        
        new_y = max(min_visible - image_height/2, new_y)
        new_y = min(canvas_height - min_visible + image_height/2, new_y)
        
        return new_x, new_y

    @staticmethod
    def calculate_selection_box(new_pos: Tuple[float, float], image_size: Tuple[int, int]) -> Tuple[float, float, float, float]:
        """
        Calcula as coordenadas da caixa de seleção.
        
        Args:
            new_pos: Nova posição da imagem (x, y)
            image_size: Dimensões da imagem (width, height)
            
        Returns:
            Tuple[float, float, float, float]: Coordenadas da caixa (x1, y1, x2, y2)
        """
        image_width, image_height = image_size
        x, y = new_pos
        
        return (
            x - image_width/2, y - image_height/2,
            x + image_width/2, y + image_height/2
        )

    @staticmethod
    def validate_pan_start(canvas_pos: Tuple[float, float], items: Tuple) -> bool:
        """
        Valida se o pan pode começar na posição especificada.
        
        Args:
            canvas_pos: Posição no canvas (x, y)
            items: Itens encontrados na posição do clique
            
        Returns:
            bool: True se o pan pode começar, False caso contrário
        """
        return len(items) > 0

    @staticmethod
    def calculate_pan_delta(current_pos: Tuple[float, float], start_pos: Tuple[float, float]) -> Tuple[float, float]:
        """
        Calcula o delta do movimento de pan.
        
        Args:
            current_pos: Posição atual do mouse (x, y)
            start_pos: Posição inicial do mouse (x, y)
            
        Returns:
            Tuple[float, float]: Delta do movimento (dx, dy)
        """
        return (
            current_pos[0] - start_pos[0],
            current_pos[1] - start_pos[1]
        )

    @staticmethod
    def analyze_image_colors(image: Image.Image) -> tuple[dict, set]:
        """
        Analisa as cores de uma imagem pixel a pixel.
        
        Args:
            image: Imagem PIL para análise
            
        Returns:
            tuple[dict, set]: (mapa de posições e cores, conjunto único de cores)
        """
        # Converte a imagem para RGB se não estiver
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Obtém os pixels da imagem
        width, height = image.size
        pixels = image.load()
        
        # Mapa de posições e cores
        color_map = {}
        # Conjunto de cores únicas
        unique_colors = set()
        
        # Analisa cada pixel
        for x in range(width):
            for y in range(height):
                color = pixels[x, y]
                # Armazena a cor no formato hexadecimal
                hex_color = '#{:02x}{:02x}{:02x}'.format(*color)
                # Adiciona ao mapa de cores
                color_map[(x, y)] = hex_color
                # Adiciona ao conjunto de cores únicas
                unique_colors.add(hex_color)
                
        return color_map, unique_colors

    @staticmethod
    def sort_colors_by_hue(colors: set) -> list:
        """
        Ordena as cores por matiz (hue).
        
        Args:
            colors: Conjunto de cores em formato hexadecimal
            
        Returns:
            list: Lista de cores ordenadas
        """
        def rgb_to_hsv(hex_color):
            # Converte hex para RGB
            r = int(hex_color[1:3], 16) / 255.0
            g = int(hex_color[3:5], 16) / 255.0
            b = int(hex_color[5:7], 16) / 255.0
            
            # Calcula HSV
            max_rgb = max(r, g, b)
            min_rgb = min(r, g, b)
            diff = max_rgb - min_rgb
            
            # Calcula matiz (hue)
            if diff == 0:
                h = 0
            elif max_rgb == r:
                h = 60 * ((g - b) / diff % 6)
            elif max_rgb == g:
                h = 60 * ((b - r) / diff + 2)
            else:
                h = 60 * ((r - g) / diff + 4)
                
            # Calcula saturação (saturation)
            s = 0 if max_rgb == 0 else diff / max_rgb
            
            # Valor (value)
            v = max_rgb
            
            return (h, s, v)
            
        # Converte cores para HSV e ordena
        return sorted(colors, key=lambda c: rgb_to_hsv(c))

    @staticmethod
    def quantize_colors(image: Image.Image, num_colors: int = 32) -> Image.Image:
        """
        Reduz o número de cores na imagem usando quantização.
        
        Args:
            image: Imagem PIL para quantização
            num_colors: Número de cores desejado
            
        Returns:
            Image.Image: Imagem com cores quantizadas
        """
        # Converte para RGB se necessário
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Quantiza a imagem
        return image.quantize(colors=num_colors, method=2).convert('RGB')

    @staticmethod
    def get_color_frequency(image: Image.Image, max_colors: int = 100) -> list:
        """
        Obtém a frequência de cada cor na imagem.
        
        Args:
            image: Imagem PIL para análise
            max_colors: Número máximo de cores a retornar
            
        Returns:
            list: Lista de tuplas (cor_hex, frequência)
        """
        # Converte para RGB se necessário
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Obtém os pixels
        pixels = list(image.getdata())
        
        # Conta a frequência de cada cor
        color_counts = {}
        total_pixels = len(pixels)
        
        for pixel in pixels:
            hex_color = '#{:02x}{:02x}{:02x}'.format(*pixel)
            color_counts[hex_color] = color_counts.get(hex_color, 0) + 1
        
        # Ordena por frequência e converte para porcentagem
        sorted_colors = sorted(
            [(color, count/total_pixels*100) for color, count in color_counts.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_colors[:max_colors]

    @staticmethod
    def cluster_colors(colors: list, threshold: float = 1.0) -> list:
        """
        Agrupa cores similares usando distância euclidiana no espaço RGB.
        
        Args:
            colors: Lista de tuplas (cor_hex, frequência)
            threshold: Limiar de similaridade (0-255)
            
        Returns:
            list: Lista de grupos de cores
        """
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
        def color_distance(c1, c2):
            r1, g1, b1 = hex_to_rgb(c1)
            r2, g2, b2 = hex_to_rgb(c2)
            return ((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2) ** 0.5
        
        clusters = []
        processed = set()
        
        for color, freq in colors:
            if color in processed:
                continue
                
            # Inicia novo cluster
            cluster = [(color, freq)]
            processed.add(color)
            
            # Procura cores similares
            for other_color, other_freq in colors:
                if other_color not in processed and color_distance(color, other_color) < threshold:
                    cluster.append((other_color, other_freq))
                    processed.add(other_color)
            
            # Adiciona cluster ordenado por frequência
            cluster.sort(key=lambda x: x[1], reverse=True)
            clusters.append(cluster)
        
        # Ordena clusters por frequência total
        clusters.sort(key=lambda x: sum(freq for _, freq in x), reverse=True)
        
        return clusters

    @staticmethod
    def analyze_image_colors_advanced(image: Image.Image) -> tuple[list, list, Image.Image]:
        """
        Realiza análise avançada das cores da imagem.
        
        Args:
            image: Imagem PIL para análise
            
        Returns:
            tuple: (cores_frequentes, grupos_de_cores, imagem_quantizada)
        """
        # Quantiza a imagem
        quantized = ImageProcessor.quantize_colors(image)
        
        # Obtém frequência das cores
        color_freq = ImageProcessor.get_color_frequency(quantized)
        
        # Agrupa cores similares
        color_clusters = ImageProcessor.cluster_colors(color_freq)
        
        return color_freq, color_clusters, quantized 