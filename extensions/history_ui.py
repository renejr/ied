import customtkinter as ctk
from tkinter import ttk
import os
from extensions.history_manager import HistoryManager

class HistoryUI:
    """
    Interface de usuário para o gerenciador de histórico.
    Adiciona botões e menus à interface principal.
    """
    
    def __init__(self, app, db_path):
        """
        Inicializa a interface do histórico.
        
        Args:
            app: Referência à aplicação principal
            db_path: Caminho para o banco de dados
        """
        self.app = app
        self.db_path = db_path
        
        # Cria o gerenciador de histórico
        self.history_manager = HistoryManager(app, db_path)
        
        # Adiciona opções ao menu
        self._add_menu_options()
        
    def _add_menu_options(self):
        """Adiciona opções ao menu"""
        # Verifica se o menu existe
        if not hasattr(self.app, 'menu'):
            return
            
        # Adiciona opções ao menu Editar
        edit_menu = self.app.menu.get_menu("Editar")
        if edit_menu:
            edit_menu.add_separator()
            edit_menu.add_command(label="Desfazer", command=self.history_manager.undo, accelerator="Ctrl+Z")
            edit_menu.add_command(label="Refazer", command=self.history_manager.redo, accelerator="Ctrl+Y")
            edit_menu.add_separator()
            edit_menu.add_command(label="Histórico de Edições", command=self.history_manager.show_history_window)
            edit_menu.add_command(label="Criar Ponto de Restauração", 
                                 command=lambda: self._show_create_restore_point_dialog())
            
    def _show_create_restore_point_dialog(self):
        """Exibe o diálogo para criar um ponto de restauração"""
        import time
        
        dialog = ctk.CTkToplevel(self.app)
        dialog.title("Criar Ponto de Restauração")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self.app)
        dialog.grab_set()
        
        # Frame principal
        main_frame = ctk.CTkFrame(dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Label de título
        title_label = ctk.CTkLabel(
            main_frame,
            text="Criar Novo Ponto de Restauração",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Frame para os campos
        fields_frame = ctk.CTkFrame(main_frame)
        fields_frame.pack(fill="x", pady=10)
        
        # Campo para nome
        name_label = ctk.CTkLabel(
            fields_frame,
            text="Nome:",
            font=("Arial", 12)
        )
        name_label.pack(anchor="w")
        
        name_entry = ctk.CTkEntry(
            fields_frame,
            width=380,
            placeholder_text="Nome do ponto de restauração"
        )
        name_entry.pack(fill="x", pady=(0, 10))
        name_entry.insert(0, f"Ponto de Restauração {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Campo para descrição
        desc_label = ctk.CTkLabel(
            fields_frame,
            text="Descrição (opcional):",
            font=("Arial", 12)
        )
        desc_label.pack(anchor="w")
        
        desc_entry = ctk.CTkEntry(
            fields_frame,
            width=380,
            placeholder_text="Descrição opcional"
        )
        desc_entry.pack(fill="x")
        
        # Botões
        buttons_frame = ctk.CTkFrame(dialog)
        buttons_frame.pack(fill="x", padx=10, pady=10)
        
        # Botão cancelar
        cancel_button = ctk.CTkButton(
            buttons_frame,
            text="Cancelar",
            command=dialog.destroy
        )
        cancel_button.pack(side="left", padx=5, expand=True, fill="x")
        
        # Botão criar
        create_button = ctk.CTkButton(
            buttons_frame,
            text="Criar",
            command=lambda: self._create_restore_point(name_entry.get(), desc_entry.get(), dialog)
        )
        create_button.pack(side="right", padx=5, expand=True, fill="x")
        
    def _create_restore_point(self, name, description, dialog):
        """Cria um ponto de restauração com os dados fornecidos"""
        from tkinter import messagebox
        
        if not name:
            messagebox.showwarning("Aviso", "Por favor, forneça um nome para o ponto de restauração.")
            return
            
        # Cria o ponto de restauração
        success = self.history_manager.create_restoration_point(name, description)
        
        if success:
            # Fecha o diálogo
            dialog.destroy()
            
            # Exibe mensagem de sucesso
            messagebox.showinfo("Sucesso", f"Ponto de restauração '{name}' criado com sucesso!")
        else:
            messagebox.showerror("Erro", "Não foi possível criar o ponto de restauração.")
            
    def _create_tooltip(self, widget, text):
        """Cria um tooltip para o widget"""
        # Implementação simples de tooltip
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25
            
            # Cria uma toplevel window
            self.tooltip = ctk.CTkToplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            
            label = ctk.CTkLabel(
                self.tooltip,
                text=text,
                justify="left",
                corner_radius=0
            )
            label.pack(ipadx=5, ipady=5)
            
        def leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)
