import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, UnidentifiedImageError, ImageFile, ImageGrab
import tempfile
import os
import platform  # Importa o módulo platform
import time
import threading
import sqlite3
import warnings
import cv2  # Importação do OpenCV para captura de dispositivos
import numpy as np  # Para conversão de arrays

# Import pywin32 components for WIA scanner support
try:
    import win32com.client
    print("win32com.client importado com sucesso")
except ImportError:
    print("Erro ao importar win32com.client. Funcionalidade WIA não estará disponível.")

# Import sys for module checking
import sys

from db import load_global_preferences, init_db, update_last_opened, save_global_preferences
from viewer_state import save_view_state, load_view_state
from preferences import (
    THUMB_CLOSE_ON_SELECT,
    THUMB_WINDOW_WIDTH,
    THUMB_WINDOW_HEIGHT,
    THUMB_WINDOW_X,
    THUMB_WINDOW_Y,
    THUMB_SIZE,
    THUMB_SHOW_INFO,
    THUMB_SORT_BY_PATH,
    THUMB_AUTO_SCROLL,
    THUMB_SHOW_INFO_BOOL,
    THUMB_SORT_BY_PATH_BOOL,
    THUMB_AUTO_SCROLL_BOOL,
    THUMB_BACKGROUND_COLOR,
    THUMB_WINDOW_BACKGROUND_COLOR,
    THUMB_BORDER_COLOR,
    THUMB_TEXT_COLOR,
    THUMB_TEXT_TEMPLATE
)
from customtkinter import CTkImage
from collections import deque  # Import deque for efficient queue
from extensions.history_ui import HistoryUI  # Adicione esta importação
import math
from image_processor import ImageProcessor
import requests
import base64
from io import BytesIO
import re
from urllib.parse import urlparse
# Add these imports at the top of the file, after the existing imports
from extensions.history_ui import HistoryUI

# Set a reasonable maximum image size limit (adjust as needed)
# This is approximately 4 times the default limit
Image.MAX_IMAGE_PIXELS = 358000000  # ~18900x18900 pixels

# Or suppress the DecompressionBombWarning if you trust your image sources
# warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)

print(f"[Miniaturas_app] Tamanho: {THUMB_SIZE}px")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

DB_PATH = "image_editor.db"

# Load schema version from preferences
conn = sqlite3.connect(DB_PATH)
try:
    cur = conn.cursor()
    cur.execute("SELECT value FROM preferences WHERE key = 'schema_version'")
    row = cur.fetchone()
    SCHEMA_VERSION = int(row[0]) if row else 0
finally:
    conn.close()

# PIL workaround para imagens incompletas
ImageFile.LOAD_TRUNCATED_IMAGES = True

class MonitorWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Monitor de Informações")
        self.geometry("400x800")  # Aumentei a altura para acomodar as novas informações
        self.parent = parent
        
        # Configurações da janela
        self.resizable(False, False)
        self.configure(fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
        
        # Frame principal
        self.main_frame = ctk.CTkFrame(self, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Labels para informações
        self.labels = {}
        self.create_labels()
        
        # Atualização periódica
        self.update_interval = 50  # ms
        self.last_mouse_pos = (0, 0)
        self.last_image_pos = (0, 0)
        self.last_update_time = time.time()
        
        self.update_info()
        
    def create_labels(self):
        """Cria os labels para exibição das informações"""
        info_items = [
            ("image_info", "Informações da Imagem:"),
            ("image_bounds", "Limites da Imagem:"),
            ("image_size_pixels", "Dimensões em Pixels:"),
            ("zoom_level", "Nível de Zoom:"),
            ("mouse_pressed", "Botão Esquerdo Pressionado:"),
            ("mouse_pos", "Posição do Mouse:"),
            ("mouse_speed_x", "Velocidade do Mouse X:"),
            ("mouse_speed_y", "Velocidade do Mouse Y:"),
            #("image_speed", "Velocidade da Imagem:")
        ]
        
        for i, (key, text) in enumerate(info_items):
            # Label do título
            title = ctk.CTkLabel(
                self.main_frame,
                text=text,
                font=("Arial", 12, "bold"),
                text_color=THUMB_TEXT_COLOR
            )
            title.pack(anchor="w", pady=(10 if i > 0 else 0, 0))
            
            # Label do valor
            value = ctk.CTkLabel(
                self.main_frame,
                text="---",
                font=("Arial", 12),
                text_color=THUMB_TEXT_COLOR,
                justify="left",
                wraplength=380
            )
            value.pack(anchor="w", padx=10)
            
            self.labels[key] = value
            
    def calculate_speed_by_axis(self, current_pos, last_pos, time_delta):
        """Calcula a velocidade em pixels por segundo para cada eixo"""
        if time_delta == 0:
            return (0, 0)
        dx = current_pos[0] - last_pos[0]
        dy = current_pos[1] - last_pos[1]
        speed_x = dx / time_delta
        speed_y = dy / time_delta
        return speed_x, speed_y
        
    def update_info(self):
        """Atualiza todas as informações"""
        try:
            current_time = time.time()
            time_delta = current_time - self.last_update_time
            
            # Informações da imagem
            if self.parent.loaded_image and self.parent.image_path:
                img = self.parent.loaded_image
                # Obtém o formato do arquivo
                formato = os.path.splitext(self.parent.image_path)[1].upper().replace(".", "")
                img_info = (
                    f"Dimensões: {img.size[0]}x{img.size[1]}\n"
                    f"Modo: {img.mode}\n"
                    f"Formato: {formato}\n"
                    f"Bits por pixel: {len(img.mode) * 8}\n"
                    f"Animado: {'Sim' if self.parent.is_animated else 'Não'}"
                )
                self.labels["image_info"].configure(text=img_info)
                
                # Obtém os limites da imagem no canvas
                image_id = self.parent.canvas.find_withtag("all")[-1]  # Último item é a imagem
                if image_id:
                    bbox = self.parent.canvas.bbox(image_id)
                    if bbox:
                        x1, y1, x2, y2 = bbox
                        bounds_info = (
                            f"X inicial: {int(x1)} pixels\n"
                            f"X final: {int(x2)} pixels\n"
                            f"Y inicial: {int(y1)} pixels\n"
                            f"Y final: {int(y2)} pixels"
                        )
                        self.labels["image_bounds"].configure(text=bounds_info)
                        
                        # Calcula dimensões em pixels
                        width_px = int(x2 - x1)
                        height_px = int(y2 - y1)
                        total_px = width_px * height_px
                        size_info = (
                            f"Largura: {width_px} pixels\n"
                            f"Altura: {height_px} pixels\n"
                            f"Total: {total_px:,} pixels"
                        )
                        self.labels["image_size_pixels"].configure(text=size_info)
                    else:
                        self.labels["image_bounds"].configure(text="Imagem não encontrada no canvas")
                        self.labels["image_size_pixels"].configure(text="---")
            else:
                self.labels["image_info"].configure(text="Nenhuma imagem carregada")
                self.labels["image_bounds"].configure(text="---")
                self.labels["image_size_pixels"].configure(text="---")
            
            # Nível de zoom
            zoom_text = f"{self.parent.zoom_level * 100:.1f}%"
            self.labels["zoom_level"].configure(text=zoom_text)
            
            # Estado do mouse
            mouse_pressed = "Sim" if self.parent._pan_start_x is not None else "Não"
            self.labels["mouse_pressed"].configure(text=mouse_pressed)
            
            # Posição do mouse
            mouse_pos = self.winfo_pointerxy()
            canvas_pos = self.parent.canvas.winfo_rootx(), self.parent.canvas.winfo_rooty()
            relative_pos = (
                mouse_pos[0] - canvas_pos[0],
                mouse_pos[1] - canvas_pos[1]
            )
            self.labels["mouse_pos"].configure(
                text=f"X: {relative_pos[0]} pixels\nY: {relative_pos[1]} pixels"
            )
            
            # Velocidade do mouse por eixo
            speed_x, speed_y = self.calculate_speed_by_axis(mouse_pos, self.last_mouse_pos, time_delta)
            self.labels["mouse_speed_x"].configure(text=f"{abs(speed_x):.1f} pixels/segundo")
            self.labels["mouse_speed_y"].configure(text=f"{abs(speed_y):.1f} pixels/segundo")
            
            self.last_mouse_pos = mouse_pos
            self.last_update_time = current_time
            
        except Exception as e:
            print(f"Erro ao atualizar monitor: {e}")
            
        finally:
            # Agenda próxima atualização
            self.after(self.update_interval, self.update_info)

class ColorPaletteWindow(ctk.CTkToplevel):
    def __init__(self, parent, color_freq, color_clusters, quantized_image):
        super().__init__(parent)
        self.title("Análise de Cores")
        self.geometry("800x600")
        
        # Configurações da janela
        self.resizable(True, True)
        self.configure(fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
        
        # Frame principal com notebook para abas
        self.notebook = ctk.CTkTabview(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Abas
        self.notebook.add("Cores Dominantes")
        self.notebook.add("Grupos de Cores")
        self.notebook.add("Imagem Quantizada")
        
        # Preenche as abas
        self.create_dominant_colors_tab(color_freq)
        self.create_color_clusters_tab(color_clusters)
        self.create_quantized_image_tab(quantized_image)
        
    def create_dominant_colors_tab(self, color_freq):
        """Cria a aba de cores dominantes"""
        tab = self.notebook.tab("Cores Dominantes")
        
        # Frame com scroll
        frame = ctk.CTkScrollableFrame(
            tab,
            fg_color=THUMB_WINDOW_BACKGROUND_COLOR
        )
        frame.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Informações
        info_label = ctk.CTkLabel(
            frame,
            text=f"Top {len(color_freq)} cores mais frequentes:",
            font=("Arial", 12, "bold"),
            text_color=THUMB_TEXT_COLOR
        )
        info_label.pack(pady=(0, 10))
        
        # Lista de cores dominantes
        for color, freq in color_freq:
            # Frame para cada cor
            color_frame = ctk.CTkFrame(
                frame,
                fg_color=THUMB_WINDOW_BACKGROUND_COLOR
            )
            color_frame.pack(fill="x", pady=2)
            
            # Amostra de cor
            sample = ctk.CTkFrame(
                color_frame,
                width=50,
                height=25,
                fg_color=color
            )
            sample.pack(side="left", padx=5)
            
            # Informações da cor
            info = ctk.CTkLabel(
                color_frame,
                text=f"{color} ({freq:.2f}%)",
                font=("Arial", 10),
                text_color=THUMB_TEXT_COLOR
            )
            info.pack(side="left", padx=5)
            
            # Bind para copiar
            for widget in [sample, info]:
                widget.bind("<Button-1>", lambda e, c=color: self.copy_color(c))
                
    def create_color_clusters_tab(self, color_clusters):
        """Cria a aba de grupos de cores"""
        tab = self.notebook.tab("Grupos de Cores")
        
        # Frame com scroll
        frame = ctk.CTkScrollableFrame(
            tab,
            fg_color=THUMB_WINDOW_BACKGROUND_COLOR
        )
        frame.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Informações
        info_label = ctk.CTkLabel(
            frame,
            text=f"{len(color_clusters)} grupos de cores similares:",
            font=("Arial", 12, "bold"),
            text_color=THUMB_TEXT_COLOR
        )
        info_label.pack(pady=(0, 10))
        
        # Lista de grupos
        for i, cluster in enumerate(color_clusters):
            # Frame para o grupo
            cluster_frame = ctk.CTkFrame(
                frame,
                fg_color=THUMB_WINDOW_BACKGROUND_COLOR
            )
            cluster_frame.pack(fill="x", pady=5)
            
            # Título do grupo
            freq_total = sum(freq for _, freq in cluster)
            title = ctk.CTkLabel(
                cluster_frame,
                text=f"Grupo {i+1} ({freq_total:.2f}%)",
                font=("Arial", 11, "bold"),
                text_color=THUMB_TEXT_COLOR
            )
            title.pack(anchor="w", padx=5, pady=(5,0))
            
            # Frame para as cores do grupo
            colors_frame = ctk.CTkFrame(
                cluster_frame,
                fg_color=THUMB_WINDOW_BACKGROUND_COLOR
            )
            colors_frame.pack(fill="x", padx=5, pady=5)
            
            # Adiciona cada cor do grupo
            for color, freq in cluster:
                # Frame para a cor
                color_frame = ctk.CTkFrame(
                    colors_frame,
                    width=30,
                    height=30,
                    fg_color=color
                )
                color_frame.pack(side="left", padx=2)
                color_frame.bind("<Button-1>", lambda e, c=color: self.copy_color(c))
                
    def create_quantized_image_tab(self, quantized_image):
        """Cria a aba da imagem quantizada"""
        tab = self.notebook.tab("Imagem Quantizada")
        
        # Frame para a imagem
        frame = ctk.CTkFrame(
            tab,
            fg_color=THUMB_WINDOW_BACKGROUND_COLOR
        )
        frame.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Redimensiona a imagem para caber na janela
        max_size = (700, 500)
        quantized_image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Converte para CTkImage
        photo = ctk.CTkImage(
            light_image=quantized_image,
            dark_image=quantized_image,
            size=quantized_image.size
        )
        
        # Label para exibir a imagem
        image_label = ctk.CTkLabel(
            frame,
            image=photo,
            text=""
        )
        image_label.image = photo  # Mantém referência
        image_label.pack(expand=True, fill="both")
        
    def copy_color(self, color):
        """Copia o código da cor para a área de transferência"""
        self.clipboard_clear()
        self.clipboard_append(color)
        messagebox.showinfo(
            "Cor Copiada",
            f"Código da cor {color} copiado para a área de transferência!"
        )

    def analyze_palette(self):
        """Analisa a paleta de cores da imagem"""
        if not self.loaded_image:
            messagebox.showwarning(
                "Sem Imagem",
                "Por favor, abra uma imagem primeiro!"
            )
            return
            
        try:
            # Inicia análise
            self.status_bar.configure(text="Analisando cores da imagem...")
            self.update_idletasks()
            
            # Realiza análise avançada
            color_freq, color_clusters, quantized = ImageProcessor.analyze_image_colors_advanced(self.loaded_image)
            
            # Atualiza status
            self.status_bar.configure(text=f"Análise concluída! {len(color_freq)} cores dominantes encontradas em {len(color_clusters)} grupos.")
            
            # Mostra a janela de paleta
            if hasattr(self, 'palette_window') and self.palette_window is not None:
                self.palette_window.destroy()
            self.palette_window = ColorPaletteWindow(self, color_freq, color_clusters, quantized)
            
        except Exception as e:
            messagebox.showerror(
                "Erro",
                f"Erro ao analisar paleta de cores: {str(e)}"
            )
            self.status_bar.configure(text="Erro ao analisar paleta de cores.")

class CreateImageWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Criar Imagem")
        self.geometry("500x300")
        self.parent = parent
        
        # Configurações da janela
        self.resizable(False, False)
        self.configure(fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
        
        # Frame principal
        self.main_frame = ctk.CTkFrame(self, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Label de título
        title = ctk.CTkLabel(
            self.main_frame,
            text="Criar Nova Imagem",
            font=("Arial", 16, "bold"),
            text_color=THUMB_TEXT_COLOR
        )
        title.pack(pady=(0, 20))
        
        # Frame para opções
        options_frame = ctk.CTkFrame(self.main_frame, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
        options_frame.pack(fill="x", pady=5)
        
        # Botão para criar a partir de URL
        url_button = ctk.CTkButton(
            options_frame,
            text="🌐 Criar a partir de URL",
            command=self.show_url_input
        )
        url_button.pack(fill="x", pady=5)
        
        # Botão para criar a partir do clipboard
        clipboard_button = ctk.CTkButton(
            options_frame,
            text="📋 Criar a partir do Clipboard",
            command=self.create_from_clipboard
        )
        clipboard_button.pack(fill="x", pady=5)

        # Botão para criar a partir de dispositivos de captura
        capture_button = ctk.CTkButton(
            options_frame,
            text="📷 Criar a partir de Dispositivos de Captura",
            command=self.show_capture_devices
        )
        capture_button.pack(fill="x", pady=5)

        # Variáveis para captura
        self.capture_devices = []
        self.selected_device = None
        self.cap = None
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.main_frame,
            text="",
            font=("Arial", 12),
            text_color=THUMB_TEXT_COLOR
        )
        self.status_label.pack(pady=10)
        
    def show_url_input(self):
        """Mostra o frame para entrada de URL"""
        # Remove widgets existentes
        for widget in self.main_frame.winfo_children():
            widget.destroy()
            
        # Label de título
        title = ctk.CTkLabel(
            self.main_frame,
            text="Criar a partir de URL",
            font=("Arial", 16, "bold"),
            text_color=THUMB_TEXT_COLOR
        )
        title.pack(pady=(0, 20))
        
        # Frame para URL
        url_frame = ctk.CTkFrame(self.main_frame, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
        url_frame.pack(fill="x", pady=5)
        
        # Label URL
        url_label = ctk.CTkLabel(
            url_frame,
            text="URL da Imagem:",
            font=("Arial", 12),
            text_color=THUMB_TEXT_COLOR
        )
        url_label.pack(anchor="w")
        
        # Entry para URL
        self.url_entry = ctk.CTkEntry(
            url_frame,
            width=400,
            placeholder_text="Cole a URL da imagem aqui"
        )
        self.url_entry.pack(fill="x", pady=5)
        
        # Botão criar
        create_button = ctk.CTkButton(
            self.main_frame,
            text="Criar Imagem",
            command=self.create_image_from_url
        )
        create_button.pack(pady=20)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.main_frame,
            text="",
            font=("Arial", 12),
            text_color=THUMB_TEXT_COLOR
        )
        self.status_label.pack(pady=10)
        
    def create_from_clipboard(self):
        """Cria uma imagem a partir do conteúdo do clipboard"""
        try:
            # Tenta obter a imagem do clipboard
            clipboard_image = ImageGrab.grabclipboard()
            
            if clipboard_image is None:
                self.status_label.configure(text="Nenhuma imagem encontrada no clipboard", text_color="red")
                return
                
            # Verifica se é uma imagem válida
            if not isinstance(clipboard_image, Image.Image):
                self.status_label.configure(text="Conteúdo do clipboard não é uma imagem válida", text_color="red")
                return
                
            # Converte para base64
            buffered = BytesIO()
            clipboard_image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Salva no banco de dados
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO imagens_criadas (fonte, img_base64) VALUES (?, ?)",
                    ("clipboard", img_base64)
                )
                conn.commit()
            finally:
                conn.close()
                
            # Atualiza a interface
            self.parent.loaded_image = clipboard_image
            self.parent.image_path = None  # Indica que é uma imagem em memória
            self.parent.image_modified = True
            self.parent.display_image()
            self.parent.update_status_bar()
            
            # Fecha a janela
            self.destroy()
            
        except Exception as e:
            self.status_label.configure(text=f"Erro ao criar imagem: {str(e)}", text_color="red")

    def is_valid_image_url(self, url):
        """Valida se a URL aponta para uma imagem válida"""
        try:
            # Verifica se a URL é válida
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                return False
                
            # Verifica a extensão do arquivo
            path = parsed.path.lower()
            valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.ico')
            if not any(path.endswith(ext) for ext in valid_extensions):
                return False
                
            return True
        except:
            return False
            
    def validate_image_header(self, response):
        """Valida se o conteúdo é realmente uma imagem"""
        content_type = response.headers.get('content-type', '')
        return content_type.startswith('image/')
        
    def create_image_from_url(self):
        """Cria uma imagem a partir da URL fornecida"""
        url = self.url_entry.get().strip()
        
        if not url:
            self.status_label.configure(text="Por favor, insira uma URL", text_color="red")
            return
            
        if not self.is_valid_image_url(url):
            self.status_label.configure(text="URL INVÁLIDA", text_color="red")
            return
            
        try:
            # Configura o status
            self.status_label.configure(text="Baixando imagem...", text_color=THUMB_TEXT_COLOR)
            self.update_idletasks()
            
            # Faz o download da imagem
            response = requests.get(url, timeout=10)
            
            # Verifica se o download foi bem sucedido
            if response.status_code != 200:
                self.status_label.configure(text="Erro ao baixar imagem", text_color="red")
                return
                
            # Valida o header da resposta
            if not self.validate_image_header(response):
                self.status_label.configure(text="TIPO DE ARQUIVO INVÁLIDO", text_color="red")
                return
                
            # Converte para base64
            img_base64 = base64.b64encode(response.content).decode('utf-8')
            
            # Salva no banco de dados
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO imagens_criadas (fonte, img_base64) VALUES (?, ?)",
                    (url, img_base64)
                )
                conn.commit()
            finally:
                conn.close()
                
            # Carrega a imagem na memória
            img = Image.open(BytesIO(response.content))
            
            # Atualiza a interface
            self.parent.loaded_image = img
            self.parent.image_path = None  # Indica que é uma imagem em memória
            self.parent.image_modified = True
            self.parent.display_image()
            self.parent.update_status_bar()
            
            # Fecha a janela
            self.destroy()
            
        except requests.RequestException as e:
            self.status_label.configure(text=f"Erro na requisição: {str(e)}", text_color="red")
        except Exception as e:
            self.status_label.configure(text=f"Erro: {str(e)}", text_color="red")

    def show_capture_devices(self):
            """Mostra os dispositivos de captura disponíveis"""
            # Remove widgets existentes
            for widget in self.main_frame.winfo_children():
                widget.destroy()
                
            # Label de título
            title = ctk.CTkLabel(
                self.main_frame,
                text="Criar a partir de Dispositivos de Captura",
                font=("Arial", 16, "bold"),
                text_color=THUMB_TEXT_COLOR
            )
            title.pack(pady=(0, 20))
            
            # Frame para dispositivos
            devices_frame = ctk.CTkFrame(self.main_frame, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
            devices_frame.pack(fill="x", pady=5)
            
            # Detecta dispositivos disponíveis
            self.detect_capture_devices()
            
            if not self.capture_devices:
                no_devices_label = ctk.CTkLabel(
                    devices_frame,
                    text="Nenhum dispositivo de captura encontrado",
                    font=("Arial", 12),
                    text_color="red"
                )
                no_devices_label.pack(pady=10)
            else:
                # Label para seleção
                select_label = ctk.CTkLabel(
                    devices_frame,
                    text="Selecione um dispositivo:",
                    font=("Arial", 12),
                    text_color=THUMB_TEXT_COLOR
                )
                select_label.pack(anchor="w", pady=(0, 5))
                
                # Combobox para seleção de dispositivo
                self.device_var = ctk.StringVar(value=self.capture_devices[0][1])
                device_combo = ctk.CTkComboBox(
                    devices_frame,
                    values=[device[1] for device in self.capture_devices],
                    variable=self.device_var,
                    width=400
                )
                device_combo.pack(fill="x", pady=5)
                
                # Botão para iniciar captura
                capture_button = ctk.CTkButton(
                    self.main_frame,
                    text="Iniciar Captura",
                    command=self.start_capture
                )
                capture_button.pack(pady=20)
            
            # Botão para voltar
            back_button = ctk.CTkButton(
                self.main_frame,
                text="Voltar",
                command=self.__init__
            )
            back_button.pack(pady=(10, 0))
            
            # Status label
            self.status_label = ctk.CTkLabel(
                self.main_frame,
                text="",
                font=("Arial", 12),
                text_color=THUMB_TEXT_COLOR
            )
            self.status_label.pack(pady=10)

    def detect_capture_devices(self):
        """Detecta dispositivos de captura disponíveis"""
        self.capture_devices = []

        try:
            # Detecta câmeras
            for i in range(3):
                try:
                    cap = cv2.VideoCapture(i, cv2.CAP_ANY)
                    if cap is not None and cap.isOpened():
                        ret, _ = cap.read()
                        if ret:
                            name = f"Câmera {i}"
                            self.capture_devices.append((i, name))
                        cap.release()
                        time.sleep(0.2)
                except Exception as device_error:
                    print(f"Aviso: Erro ao verificar dispositivo {i}: {device_error}")
                    continue

            # Tenta detectar scanners usando métodos alternativos
            try:
                    # Método 1: Tentar usar WIA (Windows Image Acquisition) para Windows
                    try:
                        print("Tentando usar WIA para scanners")
                        wia = win32com.client.Dispatch("WIA.CommonDialog")
                        # Apenas registramos a disponibilidade do WIA
                        self.capture_devices.append(("wia:scanner", "Scanner (WIA)"))
                    except ImportError:
                        print("Módulo win32com não disponível para WIA.")
                    except Exception as wia_error:
                        print(f"Erro ao inicializar WIA: {wia_error}")
            except Exception as scanner_error:
                print(f"Erro ao detectar scanners: {scanner_error}")

            if not self.capture_devices:
                if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                    self.status_label.configure(
                        text="Nenhum dispositivo de captura encontrado ou disponível",
                        text_color="red"
                    )

        except Exception as e:
            print(f"Erro geral na detecção de dispositivos: {e}")
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.configure(
                    text=f"Erro ao detectar dispositivos: {str(e)}",
                    text_color="red"
                )

    def start_capture(self):
        """Inicia a captura do dispositivo selecionado"""
        try:
            # Obtém o índice do dispositivo selecionado
            selected_name = self.device_var.get()
            selected_device = next(device for device, name in self.capture_devices if name == selected_name)
            
            # Limpa a interface
            for widget in self.main_frame.winfo_children():
                widget.destroy()
            
            # Aumenta o tamanho da janela para acomodar todos os elementos
            self.geometry("500x500")  # Aumentando a altura da janela
            
            # Cria nova interface para captura
            title = ctk.CTkLabel(
                self.main_frame,
                text=f"Capturando de: {selected_name}",
                font=("Arial", 16, "bold"),
                text_color=THUMB_TEXT_COLOR
            )
            title.pack(pady=(0, 10))
            
            # Frame para preview
            preview_frame = ctk.CTkFrame(
                self.main_frame,
                fg_color=THUMB_WINDOW_BACKGROUND_COLOR,
                width=400,
                height=300
            )
            preview_frame.pack(pady=5)
            preview_frame.pack_propagate(False)
            
            # Label para preview
            self.preview_label = ctk.CTkLabel(
                preview_frame,
                text="Iniciando dispositivo...",
                font=("Arial", 12),
                text_color=THUMB_TEXT_COLOR
            )
            self.preview_label.place(relx=0.5, rely=0.5, anchor="center")
            
            # Botão para capturar imagem
            capture_img_button = ctk.CTkButton(
                self.main_frame,
                text="📸 CAPTURAR IMAGEM",
                command=self.capture_image,
                fg_color="#28a745",
                hover_color="#218838",
                height=40
            )
            capture_img_button.pack(pady=10, fill="x", padx=20)
            
            # Botões de controle
            buttons_frame = ctk.CTkFrame(self.main_frame, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
            buttons_frame.pack(fill="x", pady=5, padx=20)
            
            # Botão para cancelar
            cancel_button = ctk.CTkButton(
                buttons_frame,
                text="❌ Cancelar",
                command=self.stop_capture
            )
            cancel_button.pack(side="right", padx=5, expand=True, fill="x")
            
            # Status label
            self.status_label = ctk.CTkLabel(
                self.main_frame,
                text="Aguardando captura...",
                font=("Arial", 12),
                text_color=THUMB_TEXT_COLOR
            )
            self.status_label.pack(pady=5)
            
            # Verifica o tipo de dispositivo e inicia a captura apropriada
            if isinstance(selected_device, int):
                # Câmera
                self.selected_device = selected_device
                self.capture_running = True
                threading.Thread(target=self.update_preview, daemon=True).start()
            elif isinstance(selected_device, str) and selected_device.startswith("scanner:"):
                # Scanner TWAIN
                self.status_label.configure(text="Iniciando scanner TWAIN...", text_color=THUMB_TEXT_COLOR)
                self.selected_device = selected_device
                # Não iniciamos preview para scanner, apenas habilitamos o botão de captura
            elif isinstance(selected_device, str) and selected_device.startswith("wia:"):
                # Scanner WIA
                self.status_label.configure(text="Iniciando scanner WIA...", text_color=THUMB_TEXT_COLOR)
                self.selected_device = selected_device
                # Não iniciamos preview para scanner, apenas habilitamos o botão de captura
                
        except Exception as e:
            self.status_label.configure(text=f"Erro ao iniciar captura: {str(e)}", text_color="red")    


    def update_preview(self):
        """Atualiza o preview da câmera"""
        try:
            # Inicializa a captura
            self.cap = cv2.VideoCapture(self.selected_device)
            
            if not self.cap.isOpened():
                self.after(0, lambda: self.status_label.configure(
                    text="Não foi possível abrir o dispositivo de captura", 
                    text_color="red"
                ) if hasattr(self, 'status_label') else None)
                return
            
            # Loop de captura
            while self.capture_running and hasattr(self, 'preview_label'):
                ret, frame = self.cap.read()
                
                if not ret:
                    break
                
                # Converte o frame para formato PIL
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                
                # Redimensiona para caber no preview
                pil_img.thumbnail((380, 280))
                
                # Converte para CTkImage
                ctk_img = CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                
                # Atualiza o preview na thread principal, mas verifica se a janela ainda existe
                if hasattr(self, 'preview_label') and self.winfo_exists():
                    self.after(0, lambda img=ctk_img: self.update_preview_ui_safe(img))
                else:
                    # Janela foi fechada, interrompe o loop
                    break
                
                # Pequena pausa para não sobrecarregar
                time.sleep(0.03)
            
            # Libera recursos
            if self.cap:
                self.cap.release()
                
        except Exception as e:
            if hasattr(self, 'status_label') and self.winfo_exists():
                self.after(0, lambda: self.status_label.configure(
                    text=f"Erro na captura: {str(e)}", 
                    text_color="red"
                ))
            print(f"Erro na captura: {str(e)}")
        
    def update_preview_ui_safe(self, img):
        """Atualiza a UI com a imagem de preview de forma segura"""
        try:
            if hasattr(self, 'preview_label') and self.preview_label.winfo_exists():
                self.preview_label.configure(image=img, text="")
                # Mantém referência para evitar coleta de lixo
                self.preview_label.image = img
        except Exception as e:
            print(f"Erro ao atualizar preview: {str(e)}")
    
    def capture_image(self):
        """Captura a imagem atual e a processa"""
        try:
            captured_image = None
            device_name = next(name for device, name in self.capture_devices if device == self.selected_device)
            
            if isinstance(self.selected_device, int):
                # Câmera
                if not self.cap or not self.cap.isOpened():
                    self.status_label.configure(text="Dispositivo de captura não disponível", text_color="red")
                    return
                    
                # Captura um frame
                ret, frame = self.cap.read()
                
                if not ret:
                    self.status_label.configure(text="Falha ao capturar imagem", text_color="red")
                    return
                
                # Converte para PIL
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                captured_image = Image.fromarray(frame_rgb)
                
            elif isinstance(self.selected_device, str) and self.selected_device.startswith("scanner:"):
                # Scanner TWAIN
                try:
                    import twain
                    self.status_label.configure(text="Abrindo scanner TWAIN...", text_color=THUMB_TEXT_COLOR)
                    
                    # Extrai o índice do scanner
                    scanner_index = int(self.selected_device.split(":")[1])
                    
                    # Inicializa o gerenciador TWAIN
                    sm = twain.SourceManager(0)
                    scanner = sm.OpenSource(sm.GetSourceList()[scanner_index])
                    
                    # Configura e inicia a digitalização
                    scanner.SetCapability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_RGB)
                    scanner.RequestAcquire(0, 0)  # UI visível
                    
                    # Obtém a imagem
                    info = scanner.GetImageInfo()
                    handle = scanner.XferImageNatively()
                    
                    if handle:
                        twain_img = twain.DIBToBMFile(handle[0], "temp_scan.bmp")
                        captured_image = Image.open("temp_scan.bmp")
                        os.remove("temp_scan.bmp")  # Remove o arquivo temporário
                    
                    # Fecha o scanner
                    scanner.destroy()
                    sm.destroy()
                    
                except Exception as twain_error:
                    self.status_label.configure(text=f"Erro TWAIN: {str(twain_error)}", text_color="red")
                    print(f"Erro detalhado TWAIN: {twain_error}")
                    return
                    
            elif isinstance(self.selected_device, str) and self.selected_device.startswith("wia:"):
                # Scanner WIA
                try:
                    import win32com.client
                    self.status_label.configure(text="Abrindo scanner WIA...", text_color=THUMB_TEXT_COLOR)
                    
                    # Inicializa o diálogo WIA
                    wia = win32com.client.Dispatch("WIA.CommonDialog")
                    device = wia.ShowSelectDevice()
                    if device:
                        # Inicia a digitalização
                        item = device.Items(1)
                        img = wia.ShowTransfer(item)
                        
                        # Salva temporariamente e carrega com PIL
                        temp_path = os.path.join(os.environ['TEMP'], "temp_scan_wia.jpg")
                        img.SaveFile(temp_path)
                        captured_image = Image.open(temp_path)
                        os.remove(temp_path)  # Remove o arquivo temporário
                        
                except Exception as wia_error:
                    self.status_label.configure(text=f"Erro WIA: {str(wia_error)}", text_color="red")
                    print(f"Erro detalhado WIA: {wia_error}")
                    return
            
            if not captured_image:
                self.status_label.configure(text="Falha ao obter imagem do dispositivo", text_color="red")
                return
                
            # Converte para base64
            buffered = BytesIO()
            captured_image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Salva no banco de dados
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO imagens_criadas (fonte, img_base64) VALUES (?, ?)",
                    (f"device:{device_name}", img_base64)
                )
                conn.commit()
            finally:
                conn.close()
            
            # Para a captura se for câmera
            if isinstance(self.selected_device, int):
                self.capture_running = False
                if self.cap:
                    self.cap.release()
                    self.cap = None
            
            # Atualiza a interface principal
            self.parent.loaded_image = captured_image
            self.parent.image_path = None  # Indica que é uma imagem em memória
            self.parent.image_modified = True
            self.parent.display_image()
            self.parent.update_status_bar()
            
            # Fecha a janela
            self.destroy()
            
        except Exception as e:
            self.status_label.configure(text=f"Erro ao processar imagem: {str(e)}", text_color="red")
            print(f"Erro detalhado: {e}")


    def stop_capture(self):
        """Para a captura e volta ao menu principal"""
        try:
            # Primeiro, sinalizamos que a captura deve parar
            self.capture_running = False
            
            # Aguarda um pouco para garantir que o thread de captura perceba a mudança
            time.sleep(0.2)  # Aumentado para dar mais tempo ao thread
            
            # Libera os recursos da câmera de forma segura
            if hasattr(self, 'cap') and self.cap is not None:
                try:
                    self.cap.release()
                except Exception as e:
                    print(f"Aviso: Erro ao liberar câmera: {e}")
                finally:
                    self.cap = None
            
            # Volta para o menu principal se a janela ainda existir
            if self.winfo_exists():
                # Limpa a interface atual
                for widget in self.main_frame.winfo_children():
                    widget.destroy()
                    
                # Reinicializa a interface com o parent correto
                self.__init__(self.parent)
                
                # Atualiza a interface para garantir que tudo seja recarregado corretamente
                self.update_idletasks()
        except Exception as e:
            print(f"Erro ao parar captura: {e}")

class ImageEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PixelArt Image Editor - Nenhuma Imagem")  # Default title
        self.geometry("1024x768")
        self.minsize(800, 600)

        # Inicialização de variáveis de imagem
        self.image_path = None
        self.loaded_image = None
        self.tk_image = None
        self.image_modified = False
        self.zoom_level = 1.0

        # Inicialização de variáveis de pan
        self._pan_start_x = None
        self._pan_start_y = None
        self._pan_image_id = None
        self._pan_image_pos = None
        self._initial_image_pos = None
        self._selection_box = None
        self._new_pos = None

        # Variável para controlar visibilidade do menu
        self.menu_visible = True
        self.toolbar = None  # Referência para a toolbar

        # Variáveis para controle do modo fullscreen
        self.is_fullscreen = False
        self.last_geometry = None  # Armazena geometria anterior

        # Add animation-related attributes initialization
        self.is_animated = False
        self.animation_frames = []
        self.current_frame = 0
        self.animation_running = False
        self.animation_speed = 100
        
        self.current_index = 0
        self.folder_files = []
        self.thumbnail_window = None
        self.thumbnail_widgets = []  # Store thumbnail widgets
        self.thumbnail_labels = []   # Store thumbnail labels

        self.fit_mode = load_global_preferences() or "fit"
        init_db()

        # Adiciona variável para a janela de monitoramento
        self.monitor_window = None

        # Cria a interface
        self.create_ui()

        # Inicializa o gerenciador de histórico (APENAS UMA VEZ)
        self.history_ui = HistoryUI(self, DB_PATH)

        # Configuração de binds
        self.bind("<Configure>", self.on_resize)
        self.bind("<Control-plus>", lambda e: self.zoom_in())
        self.bind("<Control-equal>", lambda e: self.zoom_in())
        self.bind("<Control-minus>", lambda e: self.zoom_out())
        self.bind("<Control-underscore>", lambda e: self.zoom_out())
        self.bind("<Control-0>", lambda e: self.reset_zoom())
        self.bind("<Key-t>", lambda e: self.toggle_thumbnails())
        self.bind("<Tab>", self.toggle_menu)  # Adiciona bind para TAB
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        # Carrega a última imagem aberta, se existir
        last_path = load_global_preferences("last_opened_path")
        if last_path and os.path.exists(last_path):
            self.threaded_load_image(last_path)
    
    
    def toggle_menu(self, event=None):
        """Alterna a visibilidade do menu lateral"""
        if not hasattr(self, 'toolbar_container') or not self.toolbar_container:
            return
            
        if self.menu_visible:
            # Esconde o menu
            self.toolbar_container.grid_remove()
            self.menu_visible = False
        else:
            # Mostra o menu
            self.toolbar_container.grid()
            self.menu_visible = True
            
        # Força atualização do layout
        self.update_idletasks()
        
        # Atualiza a exibição da imagem para se ajustar ao novo espaço
        if self.loaded_image:
            self.display_image()

    def toggle_thumbnails(self):
        if self.thumbnail_window and self.thumbnail_window.winfo_exists():
            self.cleanup_thumbnails()
            self.thumbnail_window.destroy()
            self.thumbnail_window = None
        else:
            if not hasattr(self, '_thumbnail_thread') or not self._thumbnail_thread.is_alive():
                self._thumbnail_thread = threading.Thread(target=self.show_thumbnails, daemon=True)
                self._thumbnail_thread.start()

    def cleanup_thumbnails(self):
        """Limpa recursos de forma segura"""
        try:
            if hasattr(self, 'thumbnails'):
                for thumb in self.thumbnails.values():
                    if thumb.get("image"):
                        thumb["image"] = None
                    if thumb.get("widget"):
                        thumb["widget"].destroy()
                self.thumbnails.clear()
            
            if hasattr(self, 'thumb_queue'):
                self.thumb_queue.clear()
            
            if hasattr(self, 'thumbnail_window') and self.thumbnail_window:
                self.thumbnail_window.destroy()
                self.thumbnail_window = None
            
        except Exception as e:
            print(f"Erro ao limpar recursos: {e}")

    def show_thumbnails(self):
        if not self.folder_files:
            print("Nenhum arquivo encontrado para miniaturas.")
            return

        def build():
            try:
                print("show_thumbnails: build() iniciado")
                if hasattr(self, 'thumbnail_window') and self.thumbnail_window:
                    self.thumbnail_window.destroy()
                
                self.thumbnail_window = ctk.CTkToplevel(self)
                self.thumbnail_window.title("Miniaturas")
                self.thumbnail_window.geometry(f"{THUMB_WINDOW_WIDTH}x{THUMB_WINDOW_HEIGHT}+{THUMB_WINDOW_X}+{THUMB_WINDOW_Y}")
                self.thumbnail_window.protocol("WM_DELETE_WINDOW", self.cleanup_thumbnails)

                # Configura o tema escuro
                self.thumbnail_window.configure(fg_color=THUMB_WINDOW_BACKGROUND_COLOR)

                # Frame principal
                main_frame = ctk.CTkFrame(self.thumbnail_window, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
                main_frame.pack(expand=True, fill="both", padx=10, pady=10)

                # Frame rolável com configuração otimizada
                self.frame = ctk.CTkScrollableFrame(
                    main_frame,
                    fg_color=THUMB_WINDOW_BACKGROUND_COLOR,
                    width=THUMB_WINDOW_WIDTH - 40,
                    height=THUMB_WINDOW_HEIGHT - 40
                )
                self.frame.pack(expand=True, fill="both")

                # Configuração do grid
                self.cols = max(1, (THUMB_WINDOW_WIDTH - 60) // (THUMB_SIZE + 20))
                for i in range(self.cols):
                    self.frame.grid_columnconfigure(i, weight=1, uniform="thumbnails")

                # Inicialização
                self.thumbnails = {}
                self.thumb_queue = deque()
                self.loading_lock = threading.Lock()
                self.is_loading = False
                
                # Criar objetos de miniatura de forma otimizada
                self.create_thumbnail_objects()

                # Iniciar carregamento em background
                self.start_background_loading()
                
                print("show_thumbnails: build() finalizado")
                
            except Exception as e:
                print(f"Erro ao construir janela de miniaturas: {e}")
                if hasattr(self, 'thumbnail_window') and self.thumbnail_window:
                    self.thumbnail_window.destroy()
                    self.thumbnail_window = None

        self.after(0, build)

    def create_thumbnail_objects(self):
        """Cria os objetos de miniatura para todas as imagens no diretório"""
        if not self.image_path or not os.path.exists(self.image_path):
            return

        # Obtém o diretório da imagem atual
        current_dir = os.path.dirname(self.image_path)
        
        # Lista apenas os arquivos que existem no diretório
        valid_files = []
        for file in self.folder_files:
            full_path = os.path.join(current_dir, file)
            if os.path.isfile(full_path):
                valid_files.append(file)  # Armazena apenas o nome do arquivo
        
        # Atualiza a lista de arquivos válidos
        self.folder_files = valid_files
        
        # Inicializa a lista de miniaturas
        self.thumbnails = {}
        
        # Configuração do grid
        self.cols = max(1, (THUMB_WINDOW_WIDTH - 60) // (THUMB_SIZE + 20))
        
        # Cria objetos de miniatura
        for i, filename in enumerate(self.folder_files):
            full_path = os.path.join(current_dir, filename)
            thumb_data = {
                "path": full_path,
                "image": None,
                "widget": None,
                "row": i // self.cols,
                "col": i % self.cols,
                "loaded": False
            }
            self.thumbnails[filename] = thumb_data
            self.thumb_queue.append(thumb_data)

    def load_single_thumbnail(self, thumb_data):
        """Carrega uma única miniatura"""
        try:
            if not hasattr(self, 'thumbnail_window') or not self.thumbnail_window:
                return

            # Cria o frame para a miniatura se não existir
            if not thumb_data["widget"]:
                thumb_data["widget"] = ctk.CTkFrame(
                    self.frame,
                    width=THUMB_SIZE,
                    height=THUMB_SIZE + 30,  # Altura extra para o texto
                    fg_color=THUMB_BACKGROUND_COLOR
                )
                
                thumb_data["widget"].grid(
                    row=thumb_data["row"],
                    column=thumb_data["col"],
                    padx=5, pady=5,
                    sticky="nsew"
                )
                
                # Força o widget a manter o tamanho
                thumb_data["widget"].grid_propagate(False)

            def process_image():
                try:
                    with Image.open(thumb_data["path"]) as img:
                        # Calcula dimensões mantendo proporção
                        width, height = img.size
                        aspect = width / height

                        if aspect > 1:
                            new_width = min(THUMB_SIZE, width)
                            new_height = int(new_width / aspect)
                        else:
                            new_height = min(THUMB_SIZE, height)
                            new_width = int(new_height * aspect)

                        # Cria a miniatura
                        thumb = img.copy()
                        thumb.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)

                        def update_ui():
                            if not hasattr(self, 'thumbnail_window') or not self.thumbnail_window:
                                return

                            # Cria a imagem CTk
                            thumb_data["image"] = CTkImage(
                                light_image=thumb,
                                dark_image=thumb,
                                size=(new_width, new_height)
                            )

                            # Frame para centralizar a imagem
                            img_frame = ctk.CTkFrame(
                                thumb_data["widget"],
                                fg_color=THUMB_BACKGROUND_COLOR,
                                height=THUMB_SIZE
                            )
                            img_frame.pack(fill="both", expand=True)
                            img_frame.pack_propagate(False)

                            # Label para a imagem
                            img_label = ctk.CTkLabel(
                                img_frame,
                                image=thumb_data["image"],
                                text="",
                                fg_color=THUMB_BACKGROUND_COLOR
                            )
                            img_label.place(relx=0.5, rely=0.5, anchor="center")

                            # Label para o nome do arquivo
                            text = os.path.basename(thumb_data["path"])
                            text_label = ctk.CTkLabel(
                                thumb_data["widget"],
                                text=text,
                                fg_color=THUMB_BACKGROUND_COLOR,
                                text_color=THUMB_TEXT_COLOR,
                                wraplength=THUMB_SIZE - 10,
                                height=30
                            )
                            text_label.pack(side="bottom", fill="x")

                            # Configura eventos de clique
                            for widget in [thumb_data["widget"], img_label, text_label]:
                                widget.bind("<Button-1>",
                                    lambda e, path=thumb_data["path"]: self.select_thumbnail(path))

                            thumb_data["loaded"] = True

                        self.after(0, update_ui)

                except Exception as e:
                    print(f"Erro ao processar miniatura {thumb_data['path']}: {e}")

            # Processa a imagem em thread separada
            threading.Thread(target=process_image, daemon=True).start()

        except Exception as e:
            print(f"Erro ao carregar miniatura {thumb_data['path']}: {e}")

    def start_background_loading(self):
        """Inicia o carregamento em background com controle de memória"""
        def load_batch():
            try:
                with self.loading_lock:
                    if self.is_loading:
                        return
                    self.is_loading = True

                batch_size = 5  # Número de miniaturas por lote
                loaded_count = 0

                while self.thumb_queue and loaded_count < batch_size:
                    if not hasattr(self, 'thumbnail_window') or not self.thumbnail_window:
                        break

                    thumb_data = self.thumb_queue.popleft()
                    if not thumb_data['loaded']:
                        self.load_single_thumbnail(thumb_data)
                        loaded_count += 1

                with self.loading_lock:
                    self.is_loading = False

                if self.thumb_queue:
                    self.after(100, load_batch)  # Agenda próximo lote

            except Exception as e:
                print(f"Erro no carregamento em background: {e}")
                with self.loading_lock:
                    self.is_loading = False

        # Inicia o primeiro lote
        self.after(100, load_batch)

    def select_thumbnail(self, path):
        if THUMB_CLOSE_ON_SELECT:
            self.thumbnail_window.destroy()
            self.thumbnail_window = None
        self.threaded_load_image(path)

    def start_pan(self, event):
        """Inicia o movimento de pan"""
        if not self.loaded_image:
            return
            
        # Encontra o item no canvas sob o cursor
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Verifica se clicou na imagem usando o ImageProcessor
        items = self.canvas.find_overlapping(x, y, x, y)
        if not ImageProcessor.validate_pan_start((x, y), items):
            return
            
        # Pega o item da imagem
        self._pan_image_id = items[-1]
        
        # Obtém as dimensões e posição atual da imagem
        bbox = self.canvas.bbox(self._pan_image_id)
        if not bbox:
            return
            
        # Armazena a posição inicial do mouse
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        
        # Armazena a posição inicial da imagem
        current_pos = self.canvas.coords(self._pan_image_id)
        if current_pos:
            self._pan_image_pos = [current_pos[0], current_pos[1]]
            self._initial_image_pos = [current_pos[0], current_pos[1]]
        else:
            # Se não conseguir obter a posição atual, usa o centro do canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            self._pan_image_pos = [canvas_width/2, canvas_height/2]
            self._initial_image_pos = [canvas_width/2, canvas_height/2]
        
        # Cria a borda de seleção usando as dimensões do bbox
        x1, y1, x2, y2 = bbox
        if hasattr(self, '_selection_box') and self._selection_box:
            self.canvas.delete(self._selection_box)
        self._selection_box = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline='#404040',
            width=2,
            dash=(2, 2),
            tags="selection"
        )
        
        # Configura o cursor
        self.canvas.config(cursor="fleur")

    def do_pan(self, event):
        """Executa o movimento de pan"""
        if not all([self._pan_image_id, self._selection_box, self._initial_image_pos]):
            return
            
        try:
            # Calcula o delta usando o ImageProcessor
            delta = ImageProcessor.calculate_pan_delta(
                (event.x, event.y),
                (self._pan_start_x, self._pan_start_y)
            )
            
            # Obtém as dimensões do canvas e da imagem
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            bbox = self.canvas.bbox(self._pan_image_id)
            if not bbox:
                return
                
            image_width = bbox[2] - bbox[0]
            image_height = bbox[3] - bbox[1]
            
            # Calcula a nova posição usando o ImageProcessor
            new_x, new_y = ImageProcessor.process_pan(
                current_pos=self._initial_image_pos,
                delta=delta,
                canvas_size=(canvas_width, canvas_height),
                image_size=(image_width, image_height),
                min_visible=50
            )
            
            # Calcula as coordenadas da caixa de seleção usando o ImageProcessor
            box_coords = ImageProcessor.calculate_selection_box(
                (new_x, new_y),
                (image_width, image_height)
            )
            
            # Move a borda de seleção
            self.canvas.coords(self._selection_box, *box_coords)
            
            # Armazena a nova posição
            self._new_pos = (new_x, new_y)
            
        except Exception as e:
            print(f"Erro durante o pan: {e}")
            self.end_pan(None)

    def end_pan(self, event):
        """Finaliza o movimento de pan"""
        try:
            if self._pan_image_id and hasattr(self, '_new_pos') and self._new_pos:
                # Move a imagem para a nova posição
                new_x, new_y = self._new_pos
                self.canvas.coords(self._pan_image_id, new_x, new_y)
                self._pan_image_pos = [new_x, new_y]
            
            # Remove a borda de seleção
            if self._selection_box:
                self.canvas.delete(self._selection_box)
            
        except Exception as e:
            print(f"Erro ao finalizar pan: {e}")
            
        finally:
            # Restaura o cursor
            self.canvas.config(cursor="")
            
            # Limpa todas as variáveis de controle
            self._pan_start_x = None
            self._pan_start_y = None
            self._pan_image_id = None
            self._pan_image_pos = None
            self._initial_image_pos = None
            self._selection_box = None
            self._new_pos = None
            
            # Salva o estado da visualização
            if self.image_path:
                save_view_state(
                    self.image_path,
                    self.zoom_level,
                    self.canvas.xview()[0],
                    self.canvas.yview()[0],
                    self.fit_mode
                )

    def create_ui(self):
        # Configuração do grid principal
        self.grid_columnconfigure(1, weight=1)  # Coluna principal expande
        self.grid_rowconfigure(0, weight=1)     # Linha principal expande

        # Bind da tecla F11 para fullscreen
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", lambda e: self.exit_fullscreen() if self.is_fullscreen else None)

        # Criação do frame para a toolbar (menu lateral)
        self.toolbar_container = ctk.CTkFrame(self, corner_radius=0, width=200)  # Defina largura fixa menor
        self.toolbar_container.grid(row=0, column=0, sticky="n")  # Alterado para "n" para alinhar ao topo
        self.toolbar_container.grid_rowconfigure(0, weight=1)
        self.toolbar_container.grid_columnconfigure(0, weight=1)
        self.toolbar_container.grid_propagate(False)  # Impede que o container se redimensione
        
        # Criação de um canvas e scrollbar para tornar a toolbar scrollável
        self.toolbar_canvas = ctk.CTkCanvas(self.toolbar_container, highlightthickness=0)
        self.toolbar_canvas.grid(row=0, column=0, sticky="nsew")
        
        self.toolbar_scrollbar = ctk.CTkScrollbar(self.toolbar_container, orientation="vertical", command=self.toolbar_canvas.yview)
        self.toolbar_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.toolbar_canvas.configure(yscrollcommand=self.toolbar_scrollbar.set)
        self.toolbar_canvas.bind("<Configure>", lambda e: self.toolbar_canvas.configure(scrollregion=self.toolbar_canvas.bbox("all")))
        
        # Criar frame interno para conter os widgets da toolbar
        self.toolbar = ctk.CTkFrame(self.toolbar_canvas, corner_radius=0, width=180)
        self.toolbar_window = self.toolbar_canvas.create_window((0, 0), window=self.toolbar, anchor="nw", width=180)
        
        # Configurar o canvas para expandir o frame interno
        self.toolbar.bind("<Configure>", self._on_toolbar_configure)
        self.toolbar_canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Habilitar scrolling com a roda do mouse
        self.toolbar_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Frame para área de visualização da imagem
        self.image_frame = ctk.CTkFrame(self)
        self.image_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.image_frame.grid_rowconfigure(0, weight=1)
        self.image_frame.grid_columnconfigure(0, weight=1)

        # Canvas para imagem - cor de fundo fixa
        self.canvas = ctk.CTkCanvas(self.image_frame, bg="#333333", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Barra de status
        self.status_bar = ctk.CTkLabel(self, text="Nenhuma imagem carregada", anchor="w")
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        # Bind events
        self.canvas.bind("<Button-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.do_pan)
        self.canvas.bind("<ButtonRelease-1>", self.end_pan)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        
        # Variáveis para controle de rotação
        self.rotation_mode = False
        self.rotation_angle = 0
        self.rotation_start_angle = 0
        self.rotation_center = None

        # Adicionar widgets no menu lateral
        self.populate_toolbar()

    def _on_toolbar_configure(self, event):
        """Atualiza o tamanho da scrollregion quando o conteúdo da toolbar muda"""
        self.toolbar_canvas.configure(scrollregion=self.toolbar_canvas.bbox("all"))
        
        # Ajusta automaticamente a altura do container do menu
        self.update_toolbar_container_height()
    
    def _on_canvas_configure(self, event):
        """Ajusta a largura do frame interno quando o canvas é redimensionado"""
        self.toolbar_canvas.itemconfig(self.toolbar_window, width=event.width)
    
    def _on_mousewheel(self, event):
        """Permite rolagem com a roda do mouse quando o mouse está sobre a toolbar"""
        # Verificar se o mouse está sobre a toolbar ou algum de seus filhos
        x, y = self.winfo_pointerxy()
        widget = self.winfo_containing(x, y)
        
        # Obtém o widget raiz do toolbar_container
        toolbar_root = self.toolbar_container.winfo_toplevel()
        
        # Verifica se o widget está na hierarquia do toolbar_container
        parent_widget = widget
        while parent_widget:
            if parent_widget == self.toolbar_container or parent_widget == self.toolbar or parent_widget == self.toolbar_canvas:
                # No Windows, event.delta contém a quantidade de rolagem
                self.toolbar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                break
            
            # Sobe na hierarquia de widgets
            try:
                parent_widget = parent_widget.master
            except:
                parent_widget = None

    def populate_toolbar(self):
        """Popula o menu lateral com botões e widgets de controle"""
        current_row = 0
        
        # Título do menu
        title_label = ctk.CTkLabel(self.toolbar, text="Pixel Art Editor", font=ctk.CTkFont(size=16, weight="bold"))
        title_label.grid(row=current_row, column=0, pady=(10, 20), padx=10)
        current_row += 1
        
        # Botões de arquivo
        load_button = ctk.CTkButton(self.toolbar, text="📂 Abrir imagem", command=self.load_image)
        load_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        # Botão Criar Imagem
        create_button = ctk.CTkButton(self.toolbar, text="🆕 Criar Imagem", command=self.show_create_image)
        create_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        save_button = ctk.CTkButton(self.toolbar, text="💾 Salvar", command=self.save_image)
        save_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        save_as_button = ctk.CTkButton(self.toolbar, text="💾 Salvar como", command=self.save_image_as)
        save_as_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1

        close_image_button = ctk.CTkButton(self.toolbar, text="❌ Fechar imagem", command=self.close_image)
        close_image_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        # Separador 1
        separator1 = ctk.CTkFrame(self.toolbar, height=2, width=180)
        separator1.grid(row=current_row, column=0, pady=10, padx=10)
        current_row += 1

        # Seção de histórico - Verificamos se o history_ui foi inicializado
        if hasattr(self, 'history_ui'):
            # Separador para histórico
            separator_history = ctk.CTkFrame(self.toolbar, height=2, width=180)
            separator_history.grid(row=current_row, column=0, pady=10, padx=10)
            current_row += 1

            # Botões de histórico
            history_label = ctk.CTkLabel(self.toolbar, text="📜 Histórico")
            history_label.grid(row=current_row, column=0, pady=(10, 0), padx=5, sticky="w")
            current_row += 1

            undo_button = ctk.CTkButton(self.toolbar, text="↩️ Desfazer", command=self.history_ui.history_manager.undo)
            undo_button.grid(row=current_row, column=0, pady=5, padx=5)
            current_row += 1

            redo_button = ctk.CTkButton(self.toolbar, text="↪️ Refazer", command=self.history_ui.history_manager.redo)
            redo_button.grid(row=current_row, column=0, pady=5, padx=5)
            current_row += 1

            history_window_button = ctk.CTkButton(self.toolbar, text="📋 Ver Histórico", 
            command=self.history_ui.history_manager.show_history_window)
            history_window_button.grid(row=current_row, column=0, pady=5, padx=5)
            current_row += 1
            
            # Separador após histórico
            separator_after_history = ctk.CTkFrame(self.toolbar, height=2, width=180)
            separator_after_history.grid(row=current_row, column=0, pady=10, padx=10)
            current_row += 1
        
        # Botão de imprimir
        print_button = ctk.CTkButton(self.toolbar, text="🖨️ Imprimir", command=self.print_image)  # Adicione este botão
        print_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1

        # Botões de navegação
        prev_button = ctk.CTkButton(self.toolbar, text="⬅ Anterior", command=self.prev_image)
        prev_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        next_button = ctk.CTkButton(self.toolbar, text="Próxima ➡", command=self.next_image)
        next_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        # Separador para navegação
        separator_nav = ctk.CTkFrame(self.toolbar, height=2, width=180)
        separator_nav.grid(row=current_row, column=0, pady=10, padx=10)
        current_row += 1
        
        # Controle de Zoom
        zoom_label = ctk.CTkLabel(self.toolbar, text="🔍 Zoom")
        zoom_label.grid(row=current_row, column=0, pady=(10, 0), padx=5, sticky="w")
        current_row += 1
        
        zoom_frame = ctk.CTkFrame(self.toolbar)
        zoom_frame.grid(row=current_row, column=0, pady=5, padx=5)
        
        zoom_out_button = ctk.CTkButton(zoom_frame, text="-", width=40, command=self.zoom_out)
        zoom_out_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.zoom_label = ctk.CTkLabel(zoom_frame, text="100%", width=60)
        self.zoom_label.grid(row=0, column=1, padx=5, pady=5)
        
        zoom_in_button = ctk.CTkButton(zoom_frame, text="+", width=40, command=self.zoom_in)
        zoom_in_button.grid(row=0, column=2, padx=5, pady=5)
        
        current_row += 1
        
        # Botões de ajuste
        adjust_width_button = ctk.CTkButton(self.toolbar, text="↔ Ajustar largura", 
        command=lambda: self.set_fit_mode("width"))
        adjust_width_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        adjust_height_button = ctk.CTkButton(self.toolbar, text="↕ Ajustar altura", 
        command=lambda: self.set_fit_mode("height"))
        adjust_height_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        adjust_screen_button = ctk.CTkButton(self.toolbar, text="🖥 Ajustar tela", 
        command=lambda: self.set_fit_mode("fit"))
        adjust_screen_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        # Separador 2
        separator2 = ctk.CTkFrame(self.toolbar, height=2, width=180)
        separator2.grid(row=current_row, column=0, pady=10, padx=10)
        current_row += 1
        
        # Botão de miniaturas
        thumbnails_button = ctk.CTkButton(self.toolbar, text="🖼 Miniaturas", command=self.toggle_thumbnails)
        thumbnails_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        # Separador 3
        separator3 = ctk.CTkFrame(self.toolbar, height=2, width=180)
        separator3.grid(row=current_row, column=0, pady=10, padx=10)
        current_row += 1
        
        # Botão de rotação
        self.rotate_button = ctk.CTkButton(self.toolbar, text="🔄 Rotacionar", command=self.toggle_rotation_mode)
        self.rotate_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        # Separador 4
        separator4 = ctk.CTkFrame(self.toolbar, height=2, width=180)
        separator4.grid(row=current_row, column=0, pady=10, padx=10)
        current_row += 1
        
        # Botão Monitor
        monitor_button = ctk.CTkButton(self.toolbar, text="📊 Monitor", command=self.toggle_monitor)
        monitor_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        # Separador 5
        separator5 = ctk.CTkFrame(self.toolbar, height=2, width=180)
        separator5.grid(row=current_row, column=0, pady=10, padx=10)
        current_row += 1
        
        # Botão Analisar Paleta
        palette_button = ctk.CTkButton(self.toolbar, text="🎨 Analisar Paleta", command=self.analyze_palette)
        palette_button.grid(row=current_row, column=0, pady=5, padx=5)
        current_row += 1
        
        # Separador 6
        separator6 = ctk.CTkFrame(self.toolbar, height=2, width=180)
        separator6.grid(row=current_row, column=0, pady=10, padx=10)
        current_row += 1
        
        # Botão Sair
        exit_button = ctk.CTkButton(self.toolbar, text="🚪 Sair", command=self.on_exit)
        exit_button.grid(row=current_row, column=0, pady=(30, 5), padx=5)
        current_row += 1

    def toggle_rotation_mode(self):
        """Alterna o modo de rotação"""
        self.rotation_mode = not self.rotation_mode
        if self.rotation_mode:
            self.rotate_button.configure(fg_color="red")  # Indica modo ativo
            # Altera os bindings do mouse para rotação
            self.canvas.unbind("<Button-1>")
            self.canvas.unbind("<B1-Motion>")
            self.canvas.bind("<Button-1>", self.start_rotation)
            self.canvas.bind("<B1-Motion>", self.update_rotation)
            self.canvas.bind("<ButtonRelease-1>", self.end_rotation)
            # Mostra mensagem de ajuda
            self.show_rotation_help()
        else:
            self.rotate_button.configure(fg_color=["#3B8ED0", "#1F6AA5"])  # Restaura cor original
            # Restaura os bindings originais
            self.canvas.unbind("<Button-1>")
            self.canvas.unbind("<B1-Motion>")
            self.canvas.bind("<Button-1>", self.start_pan)
            self.canvas.bind("<B1-Motion>", self.do_pan)
            self.canvas.bind("<ButtonRelease-1>", self.end_pan)

    def show_rotation_help(self):
        """Mostra mensagem de ajuda para rotação"""
        messagebox.showinfo("Modo Rotação", 
            "Modo de rotação ativado!\n\n"
            "- Clique e arraste para rotacionar a imagem\n"
            "- O centro de rotação será o centro da imagem\n"
            "- Clique no botão 'Rotacionar' novamente para sair do modo de rotação")

    def start_rotation(self, event):
        """Inicia a rotação"""
        if not self.loaded_image:
            return

        # Calcula o centro da imagem na tela
        bbox = self.canvas.bbox("image")
        if not bbox:
            return

        self.rotation_center = (
            (bbox[0] + bbox[2]) / 2,
            (bbox[1] + bbox[3]) / 2
        )

        # Calcula o ângulo inicial
        dx = event.x - self.rotation_center[0]
        dy = event.y - self.rotation_center[1]
        self.rotation_start_angle = math.degrees(math.atan2(dy, dx))
        self.initial_rotation = self.rotation_angle

    def update_rotation(self, event):
        """Atualiza a rotação conforme o movimento do mouse"""
        if not self.loaded_image or not self.rotation_center:
            return

        # Calcula o novo ângulo
        dx = event.x - self.rotation_center[0]
        dy = event.y - self.rotation_center[1]
        current_angle = math.degrees(math.atan2(dy, dx))
        
        # Calcula a diferença de ângulo
        delta_angle = current_angle - self.rotation_start_angle
        new_angle = (self.initial_rotation + delta_angle) % 360

        # Atualiza a rotação
        self.rotation_angle = new_angle
        self.apply_rotation()

    def end_rotation(self, event):
        """Finaliza a rotação"""
        if self.image_path:
            save_view_state(
                self.image_path,
                self.zoom_level,
                self.canvas.xview()[0],
                self.canvas.yview()[0],
                self.fit_mode
            )
        self.rotation_center = None

    def apply_rotation(self):
        """Aplica a rotação à imagem"""
        if not self.loaded_image:
            return

        # Rotaciona a imagem
        rotated_image = ImageProcessor.rotate_image(self.loaded_image, -self.rotation_angle)
        
        # Otimiza o uso de memória
        rotated_image = ImageProcessor.optimize_memory(rotated_image)
        
        self.loaded_image = rotated_image
        self.image_modified = True
        self.display_image()
        self.update_status_bar()

    def display_image(self, image=None):
        """Exibe a imagem no canvas"""
        if image is None and not self.loaded_image:
            return
            
        if image is not None:
            self.loaded_image = image

        # Calcula as novas dimensões baseadas no modo de ajuste
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        new_width, new_height = ImageProcessor.calculate_new_dimensions(
            self.loaded_image, canvas_width, canvas_height, self.fit_mode
        )
        
        # Aplica o zoom
        resized_image = ImageProcessor.resize_image(
            self.loaded_image.copy(), new_width, new_height
        )
        if self.zoom_level != 1.0:
            resized_image = ImageProcessor.apply_zoom(resized_image, self.zoom_level)
            
        # Converte para PhotoImage
        self.photo_image = ImageProcessor.convert_to_photoimage(resized_image)
        
        # Atualiza o canvas
        self.canvas.delete("all")
        image_item = self.canvas.create_image(
            canvas_width // 2, canvas_height // 2,
            image=self.photo_image, anchor="center",
            tags="image"  # Adiciona a tag "image"
        )
        
        # Armazena o ID da imagem e sua posição inicial
        self._pan_image_id = image_item
        self._pan_image_pos = [canvas_width // 2, canvas_height // 2]

        # Atualiza o título da janela
        if hasattr(self, 'image_path') and self.image_path:
            self.title(f"PixelArt Image Editor - {os.path.basename(self.image_path)}")

    def set_loading(self, is_loading):
        """Atualiza o estado de carregamento da interface"""
        if is_loading:
            self.status_bar.configure(text="Carregando imagem...")
            # Desabilita interações durante o carregamento
            if hasattr(self, 'canvas'):
                self.canvas.configure(state="disabled")
        else:
            # Restaura o estado normal
            if hasattr(self, 'canvas'):
                self.canvas.configure(state="normal")
            self.update_status_bar()

    def threaded_load_image(self, path):
        from db import update_last_opened
        def task():
            self.set_loading(True)
            try:
                self.image_path = path
                try:
                    # Load the image and check if it's animated
                    img = Image.open(self.image_path)
                    
                    # Reset animation variables
                    self.is_animated = False
                    self.animation_frames = []
                    self.current_frame = 0
                    self.animation_running = False
                    
                    # Check if this is an animated GIF
                    if getattr(img, "is_animated", False):
                        self.is_animated = True
                        self.animation_frames = []
                        
                        # Get animation speed from the first frame
                        self.animation_speed = img.info.get('duration', 100)
                        
                        # Load all frames
                        try:
                            for i in range(img.n_frames):
                                img.seek(i)
                                self.animation_frames.append(img.copy())
                            
                            # Set the first frame as the loaded image
                            self.loaded_image = self.animation_frames[0]
                            
                            # Start animation if we have frames
                            if self.animation_frames:
                                self.animation_running = True
                                self.animate_gif()
                        except Exception as e:
                            print(f"Error loading animation frames: {e}")
                            # Fallback to static image
                            self.is_animated = False
                            self.loaded_image = img.copy()
                    else:
                        # Regular non-animated image
                        self.loaded_image = img.copy()
                    
                except (FileNotFoundError, UnidentifiedImageError) as e:
                    messagebox.showerror("Erro ao abrir imagem", str(e))
                    return

                # Atualiza a interface
                self.after(0, lambda: self.title(f"PixelArt Image Editor - {os.path.basename(self.image_path)}"))
                
                view_state = load_view_state(self.image_path)
                if view_state:
                    self.zoom_level, scroll_x, scroll_y, self.fit_mode = view_state
                else:
                    self.zoom_level = self.get_fit_zoom()
                
                # Usa after para atualizar a interface na thread principal
                self.after(0, lambda: self.display_image())
                
                if view_state:
                    self.after(0, lambda: [
                        self.canvas.xview_moveto(scroll_x),
                        self.canvas.yview_moveto(scroll_y)
                    ])
                
                self.after(0, lambda: self.update_status_bar())
                update_last_opened(self.image_path)
                
            finally:
                self.after(0, lambda: self.set_loading(False))
                
        threading.Thread(target=task, daemon=True).start()

    def animate_gif(self):
        if not self.is_animated or not self.animation_running or not self.animation_frames:
            return
            
        # Move to next frame
        self.current_frame = (self.current_frame + 1) % len(self.animation_frames)
        self.loaded_image = self.animation_frames[self.current_frame]
        
        # Display the current frame
        self.display_image()
        
        # Schedule the next frame
        self.after(self.animation_speed, self.animate_gif)
    
    def update_status_bar(self):
            if not self.loaded_image or not self.image_path:
                self.status_bar.configure(text="Nenhuma imagem carregada")
                return

            width, height = self.loaded_image.size
            mode = self.loaded_image.mode
            bpp = 8 * len(mode)

            extension = os.path.splitext(self.image_path)[1].upper().replace(".", "")
            size_mb = os.path.getsize(self.image_path) / (1024 * 1024)
            timestamp = time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getmtime(self.image_path)))

            folder = os.path.dirname(self.image_path)
            valid_ext = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif", ".ico")
            self.folder_files = [f for f in os.listdir(folder) if f.lower().endswith(valid_ext)]
            self.folder_files.sort()
            self.current_index = self.folder_files.index(os.path.basename(self.image_path))

            total = len(self.folder_files)
            pos = self.current_index + 1 if total > 0 else 0

            zoom_pct = self.zoom_level * 100

            # Add animation info if applicable
            animation_info = f"🎬 {len(self.animation_frames)} frames | " if self.is_animated else ""

            modified_flag = "🔧 " if self.image_modified else ""

            status = (
                f"{modified_flag}📐 {width} x {height} | 🎨 {bpp} BPP | 🧩 {extension} | 💾 {size_mb:.2f} MB | "
                f"{animation_info}🕓 {timestamp} | 📁 {pos}/{total} | 🔍 {zoom_pct:.0f}%"
            )

            self.status_bar.configure(text=status)

    def on_resize(self, event):
        """Manipula o evento de redimensionamento da janela"""
        if event.widget == self:
            # Atualiza a altura do container do menu após o redimensionamento
            self.after(100, self.update_toolbar_container_height)
            
            # Atualiza a imagem se estiver carregada
            if self.loaded_image:
                # Agenda a atualização da imagem com um pequeno delay para evitar atualizações excessivas
                self.after(100, self.refresh_display)

    def update_toolbar_container_height(self):
        """Atualiza a altura do container do toolbar para eliminar espaços em branco"""
        if hasattr(self, 'toolbar') and hasattr(self, 'toolbar_container'):
            # Força atualização de medidas
            self.update_idletasks()
            
            # Obtém altura do conteúdo do toolbar
            height = self.toolbar.winfo_reqheight()
            
            if height > 0:
                # Obtém altura da tela e define um máximo para o menu
                screen_height = self.winfo_height() - self.status_bar.winfo_height()
                # Limita à altura da tela menos status bar e um pequeno espaço
                max_height = min(height, screen_height - 10)
                self.toolbar_container.configure(height=max_height)

    def refresh_display(self):
        """Atualiza a exibição da imagem e a barra de status"""
        if self.loaded_image:
            self.display_image()
            self.update_status_bar()

    def zoom(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
    
    def zoom_in(self):
        self.zoom_level *= 1.1
        self.display_image()
        self.update_status_bar()

    def zoom_out(self):
        self.zoom_level /= 1.1
        self.display_image()
        self.update_status_bar()

    def reset_zoom(self):
        self.zoom_level = self.get_fit_zoom()
        self.display_image()
        self.update_status_bar()

    def on_mouse_wheel(self, event):
        """Manipula o evento de rolagem do mouse para zoom"""
        if not self.loaded_image:
            return
            
        # Determina a direção do zoom baseado na direção da rolagem
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        
        # Atualiza a visualização
        self.update_status_bar()

    def get_fit_zoom(self):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if not self.loaded_image:
            return 1.0
        img_w, img_h = self.loaded_image.size
        if self.fit_mode == "width":
            return canvas_width / img_w
        elif self.fit_mode == "height":
            return canvas_height / img_h
        return min(canvas_width / img_w, canvas_height / img_h)
    
    def load_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif *.ico")]
        )
        if not file_path:
            return
            
        # Use threaded_load_image for loading the image
        self.threaded_load_image(file_path)
        
        # Check if file_path is valid before setting image_path and title
        if file_path:
            self.image_path = file_path
            self.title(f"PixelArt Image Editor - {os.path.basename(self.image_path)}")

            folder = os.path.dirname(self.image_path)
            valid_ext = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif", ".ico")
            self.folder_files = [f for f in os.listdir(folder) if f.lower().endswith(valid_ext)]
            self.folder_files.sort()
            self.current_index = self.folder_files.index(os.path.basename(file_path))

            self.loaded_image = Image.open(self.image_path)
            self.image_modified = False
            self.zoom_level = self.get_fit_zoom()
            self.display_image()
            self.update_status_bar()
        else:
            self.title("PixelArt Image Editor - Nenhuma Imagem") # Set a default title

    def set_fit_mode(self, mode):
        self.fit_mode = mode
        self.zoom_level = self.get_fit_zoom()
        self.display_image()
        self.update_status_bar()

    def save_image(self):
        if not self.loaded_image or not self.image_path:
            return
            
        # Exibe caixa de diálogo de confirmação
        response = messagebox.askyesno(
            "Confirmar Salvamento",
            f"Deseja salvar a imagem {os.path.basename(self.image_path)}?"
        )
        
        if response:
            try:
                self.loaded_image.save(self.image_path)
                self.image_modified = False
                self.update_status_bar()
                messagebox.showinfo("Sucesso", "Imagem salva com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar a imagem: {str(e)}")

    def save_image_as(self):
        if not self.loaded_image:
            return
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
            self.image_path = file_path
            self.loaded_image.save(file_path)
            self.image_path = file_path
            self.title(f"PixelArt Image Editor - {os.path.basename(self.image_path)}")
            self.image_modified = False
            self.update_status_bar()

    def prev_image(self):
            if self.current_index > 0:
                save_view_state(
                    self.image_path,
                    self.zoom_level,
                    self.canvas.xview()[0],
                    self.canvas.yview()[0],
                    self.fit_mode
                )
                self.current_index -= 1
                folder = os.path.dirname(self.image_path)
                filename = self.folder_files[self.current_index]
                self.threaded_load_image(os.path.join(folder, filename))

    def next_image(self):
        if self.current_index < len(self.folder_files) - 1:
            save_view_state(
                self.image_path,
                self.zoom_level,
                self.canvas.xview()[0],
                self.canvas.yview()[0],
                self.fit_mode
            )
            self.current_index += 1
            folder = os.path.dirname(self.image_path)
            filename = self.folder_files[self.current_index]
            self.threaded_load_image(os.path.join(folder, filename))

    def open_image_by_index(self):
        save_view_state(
            self.image_path,
            self.zoom_level,
            self.canvas.xview()[0],
            self.canvas.yview()[0],
            self.fit_mode
        )
        folder = os.path.dirname(self.image_path)
        filename = self.folder_files[self.current_index]
        self.image_path = os.path.join(folder, filename)
        self.title(f"PixelArt Image Editor - {os.path.basename(self.image_path)}")
        self.loaded_image = Image.open(self.image_path)
        self.image_modified = False
        self.load_view_state()
        self.update_status_bar()

    def on_exit(self):
        # Stop animation before exiting
        self.animation_running = False
        
        if not self.loaded_image:
            if self.image_path:
                save_global_preferences("last_opened_path", self.image_path)
            self.destroy()
            return
        
        if self.image_modified:
            response = messagebox.askyesnocancel(
                "Sair e salvar imagem?",
                "Você deseja salvar a imagem antes de sair?"
            )

            if response is True:
                self.save_image()
                self.destroy()
            elif response is False:
                self.destroy()
            else:
                return
        else:
            self.destroy()

    def toggle_monitor(self):
        """Alterna a exibição da janela de monitoramento"""
        if self.monitor_window and self.monitor_window.winfo_exists():
            self.monitor_window.destroy()
            self.monitor_window = None
        else:
            self.monitor_window = MonitorWindow(self)

    def analyze_palette(self):
        """Analisa a paleta de cores da imagem"""
        if not self.loaded_image:
            messagebox.showwarning(
                "Sem Imagem",
                "Por favor, abra uma imagem primeiro!"
            )
            return
            
        try:
            # Inicia análise
            self.status_bar.configure(text="Analisando cores da imagem...")
            self.update_idletasks()
            
            # Realiza análise avançada
            color_freq, color_clusters, quantized = ImageProcessor.analyze_image_colors_advanced(self.loaded_image)
            
            # Atualiza status
            self.status_bar.configure(text=f"Análise concluída! {len(color_freq)} cores dominantes encontradas em {len(color_clusters)} grupos.")
            
            # Mostra a janela de paleta
            if hasattr(self, 'palette_window') and self.palette_window is not None:
                self.palette_window.destroy()
            self.palette_window = ColorPaletteWindow(self, color_freq, color_clusters, quantized)
            
        except Exception as e:
            messagebox.showerror(
                "Erro",
                f"Erro ao analisar paleta de cores: {str(e)}"
            )
            self.status_bar.configure(text="Erro ao analisar paleta de cores.")

    def toggle_fullscreen(self, event=None):
        """Alterna entre modo tela cheia e normal"""
        if not self.is_fullscreen:
            # Salva a geometria atual antes de ir para fullscreen
            self.last_geometry = self.geometry()
            # Entra em modo fullscreen
            self.attributes('-fullscreen', True)
            self.is_fullscreen = True
        else:
            self.exit_fullscreen()
            
        # Força atualização completa do layout
        self.update_idletasks()
        
        # Reconfigura a scrollregion do toolbar_canvas
        self.toolbar_canvas.configure(scrollregion=self.toolbar_canvas.bbox("all"))
        
        # Ajusta a altura do container do menu
        self.update_toolbar_container_height()
        
        # Atualiza a exibição da imagem para se ajustar ao novo tamanho
        if self.loaded_image:
            self.display_image()

    def exit_fullscreen(self):
        """Sai do modo tela cheia"""
        if self.is_fullscreen:
            # Desativa modo fullscreen
            self.attributes('-fullscreen', False)
            # Restaura geometria anterior
            if self.last_geometry:
                self.geometry(self.last_geometry)
            self.is_fullscreen = False

    def close_image(self):
        """Fecha a imagem atualmente carregada"""
        if self.loaded_image:
            self.loaded_image = None
            self.image_path = None
            self.canvas.delete("all")
            self.status_bar.configure(text="Nenhuma imagem carregada")
            self.title("PixelArt Image Editor - Nenhuma Imagem")
            self.update_status_bar()

    # Modify the apply_filter method to record actions in the history
    def apply_filter(self, filter_name, **kwargs):
        if not self.loaded_image:
            return
            
        # Save the current state before applying the filter
        if hasattr(self, 'history_ui'):
            self.history_ui.history_manager.create_restoration_point(f"Before {filter_name}")
        
        # ... existing filter application code ...
        
        # Record the action in history
        if hasattr(self, 'history_ui'):
            self.history_ui.history_manager.add_action('filter', {'name': filter_name, 'params': kwargs}, f"Applied filter: {filter_name}")

    def show_create_image(self):
        """Mostra a janela de criação de imagem"""
        if hasattr(self, 'create_window') and self.create_window is not None:
            self.create_window.destroy()
        self.create_window = CreateImageWindow(self)            

    def print_image(self):
        """Print the currently loaded image."""
        if self.loaded_image is None:
            messagebox.showerror("Erro", "Nenhuma imagem carregada para imprimir.")
            return

        # Convert the image to a format suitable for printing
        try:
            # Convert to RGB if not already in that mode
            if self.loaded_image.mode != "RGB":
                image_to_print = self.loaded_image.convert("RGB")
            else:
                image_to_print = self.loaded_image

            # Save the image to a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            image_to_print.save(temp_file.name, "PNG")
            temp_file.close()

            # Use the default printer to print the image
            os.startfile(temp_file.name, "print")

        except Exception as e:
            messagebox.showerror("Erro de Impressão", f"Erro ao tentar imprimir a imagem: {e}")

if __name__ == "__main__":
    init_db()
    app = ImageEditorApp()
    app.mainloop()
    app.mainloop()