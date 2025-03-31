import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, UnidentifiedImageError, ImageFile
import os
import time
import threading
import sqlite3
import warnings
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

class ImageEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PixelArt Image Editor - Nenhuma Imagem")  # Default title
        self.geometry("1024x768")
        self.minsize(800, 600)

        self.image_path = None
        self.loaded_image = None
        self.tk_image = None
        self.image_modified = False
        self.zoom_level = 1.0

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

        last_path = load_global_preferences("last_opened_path")
        if last_path and os.path.exists(last_path):
            self.threaded_load_image(last_path)

        self.create_ui()
        self.bind("<Configure>", self.on_resize)
        self.bind("<Control-plus>", lambda e: self.zoom_in())
        self.bind("<Control-equal>", lambda e: self.zoom_in())
        self.bind("<Control-minus>", lambda e: self.zoom_out())
        self.bind("<Control-underscore>", lambda e: self.zoom_out())
        self.bind("<Control-0>", lambda e: self.reset_zoom())
        self.bind("<Key-t>", lambda e: self.toggle_thumbnails())
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        self._pan_start_x = 0
        self._pan_start_y = 0

    def toggle_thumbnails(self):
        if self.thumbnail_window and self.thumbnail_window.winfo_exists():
            self.thumbnail_window.destroy()
            self.thumbnail_window = None
        else:
            threading.Thread(target=self.show_thumbnails, daemon=True).start()

    def show_thumbnails(self):
        if not self.folder_files:
            return

        def build():
            print("show_thumbnails: build() started")  # Debug print
            self.thumbnail_window = ctk.CTkToplevel(self)
            self.thumbnail_window.title("Miniaturas")
            self.thumbnail_window.geometry(f"{THUMB_WINDOW_WIDTH}x{THUMB_WINDOW_HEIGHT}+{THUMB_WINDOW_X}+{THUMB_WINDOW_Y}")
            self.thumbnail_window.lift()
            self.thumbnail_window.focus_force()

            # Apply the window background color
            self.thumbnail_window.configure(fg_color=THUMB_WINDOW_BACKGROUND_COLOR)

            # Create a main frame with padding
            main_frame = ctk.CTkFrame(self.thumbnail_window, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
            main_frame.pack(expand=True, fill="both", padx=10, pady=10)

            # Create scrollable frame with matching background
            self.frame = ctk.CTkScrollableFrame(main_frame, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
            self.frame.pack(expand=True, fill="both")

            # Configure grid layout with consistent spacing
            self.cols = 5  # Number of columns in the grid
            for i in range(self.cols):
                self.frame.grid_columnconfigure(i, weight=1, uniform="thumbnails")

            # Add header if needed
            if THUMB_SHOW_INFO_BOOL:
                label = ctk.CTkLabel(self.frame, text=f"[Miniaturas] Tamanho: {THUMB_SIZE}px", 
                                    anchor="w", fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
                label.grid(row=0, column=0, columnspan=self.cols, sticky="w", pady=(0, 10))
                self.start_row = 1
            else:
                self.start_row = 0

            # Calculate the fixed size for thumbnails
            self.thumb_size = THUMB_SIZE
            self.cell_padding = 5

            self.thumbnails = []
            self.visible_thumbnails = []
            self.first_visible_row = 0
            self.last_visible_row = 0
            self.max_rows = 0

            self.create_thumbnail_objects()
            self.calculate_visible_rows()
            self.render_visible_thumbnails()

            self.frame.bind("<Configure>", self.on_frame_configure)
            self.frame.bind("<MouseWheel>", self.on_mouse_wheel)
            print("show_thumbnails: build() finished")  # Debug print

        print("show_thumbnails: started")  # Debug print
        self.after(0, build)
        print("show_thumbnails: finished")  # Debug print

    def create_thumbnail_objects(self):
        for i, fname in enumerate(self.folder_files):
            full_path = os.path.join(os.path.dirname(self.image_path), fname)
            self.thumbnails.append({
                "path": full_path,
                "image": None,
                "widget": None,
                "label": None,
                "row": (i // self.cols) + self.start_row,
                "col": i % self.cols
            })
            self.max_rows = (i // self.cols) + self.start_row

    def calculate_visible_rows(self):
        try:
            self.first_visible_row = int(self.frame.yview()[0] * self.max_rows)
            self.last_visible_row = int(self.frame.yview()[1] * self.max_rows) + 1
        except AttributeError:
            # Handle the case where self.frame is not yet initialized
            self.first_visible_row = 0
            self.last_visible_row = 1

    def render_visible_thumbnails(self):
        for thumb_data in self.visible_thumbnails:
            if thumb_data["widget"]:
                thumb_data["widget"].grid_forget()
                thumb_data["label"].grid_forget()
        self.visible_thumbnails = []

        for thumb_data in self.thumbnails:
            if self.first_visible_row <= thumb_data["row"] <= self.last_visible_row:
                self.visible_thumbnails.append(thumb_data)
                if not thumb_data["widget"]:
                    thumb_data["widget"] = ctk.CTkFrame(self.frame, fg_color=THUMB_BACKGROUND_COLOR,
                                                    width=self.thumb_size, height=self.thumb_size)
                    thumb_data["label"] = ctk.CTkLabel(thumb_data["widget"], text="", fg_color=THUMB_BACKGROUND_COLOR)
                    self.thumbnail_widgets.append(thumb_data["widget"])  # Keep track of widgets
                    self.thumbnail_labels.append(thumb_data["label"])    # Keep track of labels
                
                thumb_data["widget"].grid(row=thumb_data["row"], column=thumb_data["col"],
                                        padx=self.cell_padding, pady=self.cell_padding, sticky="nsew")
                
                # Configure grid layout within the thumbnail frame
                thumb_data["widget"].grid_rowconfigure(0, weight=1)  # Image expands vertically
                thumb_data["widget"].grid_rowconfigure(1, weight=0)  # Label at bottom
                thumb_data["widget"].grid_columnconfigure(0, weight=1) # Center horizontally

                thumb_data["label"].grid(row=1, column=0, sticky="ew") # Label at bottom
                
                if not thumb_data["image"]:
                    try:
                        with Image.open(thumb_data["path"]) as img:
                            width, height = img.size
                            aspect = width / height
                            
                            # Calculate new dimensions to fit within the thumbnail size
                            if aspect > 1:
                                new_width = min(self.thumb_size, width)
                                new_height = int(new_width / aspect)
                            else:
                                new_height = min(self.thumb_size, height)
                                new_width = int(new_height * aspect)
                            
                            img.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)
                            thumb_copy = img.copy()
                        thumb_data["image"] = CTkImage(light_image=thumb_copy, size=(new_width, new_height))
                        
                    except Exception as e:
                        print(f"Error loading thumbnail for {thumb_data['path']}: {e}")
                        continue
                
                thumb_data["label"].configure(image=thumb_data["image"],
                                            text_color=THUMB_TEXT_COLOR,
                                            text=os.path.basename(thumb_data["path"]),
                                            wraplength=self.thumb_size - 10,
                                            anchor="center")  # Center the text
                
                # Make the whole frame clickable
                thumb_data["widget"].bind("<Button-1>", lambda e, f=thumb_data["path"]: self.select_thumbnail(f))
                thumb_data["label"].bind("<Button-1>", lambda e, f=thumb_data["path"]: self.select_thumbnail(f))

    def select_thumbnail(self, path):
        if THUMB_CLOSE_ON_SELECT:
            self.thumbnail_window.destroy()
            self.thumbnail_window = None
        self.threaded_load_image(path)

    def start_pan(self, event):
        self._pan_start_x = event.x
        self._pan_start_y = event.y

    def do_pan(self, event):
        dx = self._pan_start_x - event.x
        dy = self._pan_start_y - event.y
        self.canvas.xview_scroll(int(dx), "units")
        self.canvas.yview_scroll(int(dy), "units")
        self._pan_start_x = event.x
        self._pan_start_y = event.y

    def create_ui(self):
        self.toolbar = ctk.CTkFrame(self)
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.btn_prev = ctk.CTkButton(self.toolbar, text="⬅ Anterior", command=self.prev_image)
        self.btn_prev.pack(side="left", padx=5, pady=5)

        self.btn_next = ctk.CTkButton(self.toolbar, text="Próxima ➡", command=self.next_image)
        self.btn_next.pack(side="left", padx=5, pady=5)

        self.progress_label = ctk.CTkLabel(self.toolbar, text="")
        self.progress_label.pack(side="right", padx=10)

        sidebar = ctk.CTkFrame(self, width=200)
        sidebar.grid(row=0, column=0, sticky="ns")

        buttons = [
            ("🎮 Ferramentas", None, {"font": ("Consolas", 16, "bold"), "pady": 10}),
            ("📂 Abrir imagem", self.load_image),
            ("📅 Salvar", self.save_image),
            ("📅 Salvar como", self.save_image_as),
            ("➕ Zoom In", self.zoom_in),
            ("➖ Zoom Out", self.zoom_out),
            ("📏 Ajustar largura", lambda: self.set_fit_mode("width")),
            ("📐 Ajustar altura", lambda: self.set_fit_mode("height")),
            ("📎 Ajustar tela", lambda: self.set_fit_mode("fit")),
            ("🖼 Miniaturas", self.toggle_thumbnails),
            ("🎨 Filtros", None),
            ("🔼 Anterior", self.prev_image),
            ("🔽 Próxima", self.next_image),
            ("🚪 Sair", self.on_exit, {"pady": 30}),
        ]

        for text, command, *extra in buttons:
            options = extra[0] if extra else {}
            widget = ctk.CTkLabel(sidebar, text=text, **options) if command is None else ctk.CTkButton(sidebar, text=text, command=command)
            widget.pack(fill="x", padx=10, pady=5 if "pady" not in options else options["pady"])

        main_area = ctk.CTkFrame(self)
        main_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=(10, 0))
        main_area.rowconfigure(0, weight=1)
        main_area.columnconfigure(0, weight=1)

        self.canvas_container = ctk.CTkFrame(main_area)
        self.canvas_container.grid(row=0, column=0, sticky="nsew")
        self.canvas_container.rowconfigure(0, weight=1)
        self.canvas_container.columnconfigure(0, weight=1)

        self.canvas = ctk.CTkCanvas(self.canvas_container, bg="black")
        self.h_scroll = ctk.CTkScrollbar(self.canvas_container, orientation="horizontal", command=self.canvas.xview)
        self.v_scroll = ctk.CTkScrollbar(self.canvas_container, orientation="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")

        # Use lambda binding to call zoom functions
        self.canvas.bind("<MouseWheel>", lambda event: self.zoom(event))
        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.do_pan)

        self.status_bar = ctk.CTkLabel(self, text="Nenhuma imagem carregada", anchor="w")
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="sew", padx=10, pady=5)


    def set_loading(self, is_loading):
            if is_loading:
                self.btn_prev.configure(state="disabled")
                self.btn_next.configure(state="disabled")
                self.progress_label.configure(text="Carregando imagem...")
            else:
                self.btn_prev.configure(state="normal")
                self.btn_next.configure(state="normal")
                self.progress_label.configure(text="")

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
                self.title(f"PixelArt Image Editor - {os.path.basename(self.image_path)}")
                view_state = load_view_state(self.image_path)
                if view_state:
                    self.zoom_level, scroll_x, scroll_y, self.fit_mode = view_state
                else:
                    self.zoom_level = self.get_fit_zoom()
                self.display_image()
                if view_state:
                    self.canvas.xview_moveto(scroll_x)
                    self.canvas.yview_moveto(scroll_y)
                self.update_status_bar()
                update_last_opened(self.image_path)
            finally:
                self.set_loading(False)
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
    
    def display_image(self):
        if self.loaded_image:
            try:
                img = self.loaded_image.copy()
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                new_size = (int(img.width * self.zoom_level), int(img.height * self.zoom_level))
                img = img.resize(new_size, Image.LANCZOS)

                self.tk_image = ImageTk.PhotoImage(img)
                self.canvas.delete("all")
                self.canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))

                # Calculate the center coordinates
                x = (canvas_width - new_size[0]) // 2
                y = (canvas_height - new_size[1]) // 2

                self.canvas.create_image(x, y, image=self.tk_image, anchor="nw")

            except OSError:
                messagebox.showerror("Erro", "Imagem corrompida ou incompleta. Não foi possível exibir.")

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
        if event.widget == self:
            # Correctly call the methods within the class context
            self.after(100, lambda: [self.display_image(), self.update_status_bar()])

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
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

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
        self.loaded_image.save(self.image_path)
        self.image_modified = False
        self.update_status_bar()

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

    def on_frame_configure(self, event):
        self.calculate_visible_rows()
        self.render_visible_thumbnails()

    def on_mouse_wheel(self, event):
        self.calculate_visible_rows()
        self.render_visible_thumbnails()

if __name__ == "__main__":
    app = ImageEditorApp()
    app.mainloop()