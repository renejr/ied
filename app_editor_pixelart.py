# file: app_editor_pixelart.py
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, UnidentifiedImageError
import os
import time
import threading
import sqlite3
from db import load_global_preferences, init_db, update_last_opened, save_global_preferences
from viewer_state import save_view_state, load_view_state
from customtkinter import CTkImage

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

DB_PATH = "image_editor.db"
SCHEMA_VERSION = 4

class ImageEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PixelArt Image Editor")
        self.geometry("1024x768")
        self.minsize(800, 600)

        self.image_path = None
        self.loaded_image = None
        self.tk_image = None
        self.image_modified = False
        self.zoom_level = 1.0

        self.current_index = 0
        self.folder_files = []

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
        self.bind("<Key-t>", lambda e: self.show_thumbnails())
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        self._pan_start_x = 0
        self._pan_start_y = 0

    def show_thumbnails(self):
        if not self.folder_files:
            return

        top = ctk.CTkToplevel(self)
        top.title("Miniaturas")
        frame = ctk.CTkScrollableFrame(top)
        frame.pack(expand=True, fill="both", padx=10, pady=10)

        for i, fname in enumerate(self.folder_files):
            full_path = os.path.join(os.path.dirname(self.image_path), fname)
            try:
                img = Image.open(full_path)
                img.thumbnail((128, 128))
                preview = CTkImage(light_image=img.copy())
                btn = ctk.CTkButton(frame, image=preview, text=fname, compound="top",
                                    command=lambda f=full_path: [top.destroy(), self.threaded_load_image(f)])
                btn.grid(row=i // 5, column=i % 5, padx=5, pady=5)
            except Exception:
                continue

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

        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
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
                    self.loaded_image = Image.open(self.image_path)
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

    def update_status_bar(self):
        from viewer_state import load_view_state
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

        view_state = load_view_state(self.image_path)
        last_opened_fmt = ""
        if view_state:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT last_opened FROM images WHERE path = ?", (self.image_path,))
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                last_opened_fmt = time.strftime("%d/%m/%Y %H:%M", time.strptime(row[0], "%Y-%m-%d %H:%M:%S"))

        modified_flag = "🔧 " if self.image_modified else ""

        status = (
            f"{modified_flag}📐 {width} x {height} | 🎨 {bpp} BPP | 🧩 {extension} | 💾 {size_mb:.2f} MB | "
            f"🕓 {timestamp} | 📁 {pos}/{total} | 🔍 {zoom_pct:.0f}% | ⏱ Acessado: {last_opened_fmt}"
        )

        self.status_bar.configure(text=status)
        
    def display_image(self):
        if self.loaded_image:
            try:
                img = self.loaded_image.copy()
                new_size = (int(img.width * self.zoom_level), int(img.height * self.zoom_level))
                img = img.resize(new_size, Image.LANCZOS)

                self.tk_image = ImageTk.PhotoImage(img)
                self.canvas.delete("all")
                self.canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))
                self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
                self.canvas.xview_moveto(0.5 - (self.canvas.winfo_width() / (2 * new_size[0])))
                self.canvas.yview_moveto(0.5 - (self.canvas.winfo_height() / (2 * new_size[1])))
            except OSError:
                messagebox.showerror("Erro", "Imagem corrompida ou incompleta. Não foi possível exibir.")

    def on_resize(self, event):
        if event.widget == self:
            self.after(100, lambda: [self.display_image(), self.update_status_bar()])

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

if __name__ == "__main__":
    app = ImageEditorApp()
    app.mainloop()
