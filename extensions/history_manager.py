import sqlite3
import os
import io
import customtkinter as ctk
from tkinter import ttk  # Add this import
from PIL import Image
import time
import json

class HistoryManager:
    """
    Gerenciador de histórico para o editor de imagens.
    Fornece funcionalidades de desfazer/refazer, visualização de histórico
    e pontos de restauração.
    """
    
    def __init__(self, app, db_path):
        """
        Inicializa o gerenciador de histórico.
        
        Args:
            app: Referência à aplicação principal
            db_path: Caminho para o banco de dados
        """
        self.app = app
        self.db_path = db_path
        self.max_history_size = 30  # Número máximo de ações no histórico
        self.current_image_id = None
        self.current_position = 0
        self.max_position = 0
        self.history_window = None
        self.action_in_progress = False
        
        # Inicializa o estado do histórico quando uma imagem é carregada
        self.app.bind("<<ImageLoaded>>", self.on_image_loaded)
        
    def on_image_loaded(self, event=None):
        """Atualiza o estado do histórico quando uma nova imagem é carregada"""
        if self.app.image_path:
            # Obtém o ID da imagem atual
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute("SELECT id FROM images WHERE path = ?", (self.app.image_path,))
                row = cur.fetchone()
                if row:
                    self.current_image_id = row[0]
                    # Carrega o estado do histórico
                    self._load_history_state()
                else:
                    self.current_image_id = None
            finally:
                conn.close()
        else:
            self.current_image_id = None
            
        # Atualiza a interface
        self._update_ui()
    
    def _load_history_state(self):
        """Carrega o estado atual do histórico para a imagem atual"""
        if not self.current_image_id:
            self.current_position = 0
            self.max_position = 0
            return
            
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            # Verifica se já existe um estado para esta imagem
            cur.execute("SELECT current_position, max_position FROM history_state WHERE image_id = ?", 
                       (self.current_image_id,))
            row = cur.fetchone()
            
            if row:
                self.current_position = row[0]
                self.max_position = row[1]
            else:
                # Cria um novo estado
                self.current_position = 0
                self.max_position = 0
                cur.execute("INSERT INTO history_state (image_id, current_position, max_position) VALUES (?, 0, 0)",
                           (self.current_image_id,))
                conn.commit()
        finally:
            conn.close()
    
    def _save_history_state(self):
        """Salva o estado atual do histórico no banco de dados"""
        if not self.current_image_id:
            return
            
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("UPDATE history_state SET current_position = ?, max_position = ? WHERE image_id = ?",
                       (self.current_position, self.max_position, self.current_image_id))
            conn.commit()
        finally:
            conn.close()
    
    def add_action(self, action_type, action_data=None, description=None):
        """
        Adiciona uma nova ação ao histórico.
        
        Args:
            action_type: Tipo da ação (ex: 'filter', 'crop', 'resize')
            action_data: Dados da ação em formato JSON ou bytes
            description: Descrição da ação
        """
        if self.action_in_progress or not self.current_image_id:
            return
            
        # Se estamos no meio do histórico, remove todas as ações futuras
        if self.current_position < self.max_position:
            self._truncate_future_actions()
            
        # Serializa os dados da ação se necessário
        if action_data is not None and not isinstance(action_data, (bytes, bytearray)):
            action_data = json.dumps(action_data).encode('utf-8')
            
        # Adiciona a ação ao banco de dados
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO history_actions (image_id, action_type, action_data, description) VALUES (?, ?, ?, ?)",
                (self.current_image_id, action_type, action_data, description)
            )
            conn.commit()
            
            # Atualiza a posição atual
            self.current_position += 1
            self.max_position = self.current_position
            
            # Limita o tamanho do histórico
            self._limit_history_size()
            
            # Salva o estado
            self._save_history_state()
            
            # Atualiza a interface
            self._update_ui()
            
        finally:
            conn.close()
    
    def _truncate_future_actions(self):
        """Remove todas as ações futuras quando uma nova ação é adicionada no meio do histórico"""
        if not self.current_image_id:
            return
            
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            
            # Obtém os IDs das ações a serem removidas
            cur.execute(
                """SELECT id FROM history_actions 
                   WHERE image_id = ? 
                   ORDER BY id DESC 
                   LIMIT ?""",
                (self.current_image_id, self.max_position - self.current_position)
            )
            
            action_ids = [row[0] for row in cur.fetchall()]
            
            # Remove as ações
            if action_ids:
                placeholders = ','.join(['?'] * len(action_ids))
                cur.execute(f"DELETE FROM history_actions WHERE id IN ({placeholders})", action_ids)
                conn.commit()
                
        finally:
            conn.close()
    
    def _limit_history_size(self):
        """Limita o tamanho do histórico ao máximo definido"""
        if not self.current_image_id:
            return
            
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            
            # Conta quantas ações existem para esta imagem
            cur.execute("SELECT COUNT(*) FROM history_actions WHERE image_id = ?", (self.current_image_id,))
            count = cur.fetchone()[0]
            
            # Se exceder o limite, remove as ações mais antigas
            if count > self.max_history_size:
                # Obtém os IDs das ações mais antigas
                cur.execute(
                    """SELECT id FROM history_actions 
                       WHERE image_id = ? 
                       ORDER BY timestamp ASC 
                       LIMIT ?""",
                    (self.current_image_id, count - self.max_history_size)
                )
                
                action_ids = [row[0] for row in cur.fetchall()]
                
                # Remove as ações
                if action_ids:
                    placeholders = ','.join(['?'] * len(action_ids))
                    cur.execute(f"DELETE FROM history_actions WHERE id IN ({placeholders})", action_ids)
                    conn.commit()
                    
                    # Ajusta a posição atual
                    self.current_position = max(0, self.current_position - len(action_ids))
                    self.max_position = max(0, self.max_position - len(action_ids))
                    self._save_history_state()
                
        finally:
            conn.close()
    
    def undo(self):
        """Desfaz a última ação"""
        if self.action_in_progress or not self.current_image_id or self.current_position <= 0:
            return False
            
        self.action_in_progress = True
        
        try:
            # Decrementa a posição atual
            self.current_position -= 1
            
            # Obtém a ação a ser desfeita
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """SELECT action_type, action_data 
                       FROM history_actions 
                       WHERE image_id = ? 
                       ORDER BY timestamp DESC 
                       LIMIT 1 OFFSET ?""",
                    (self.current_image_id, self.max_position - self.current_position - 1)
                )
                
                row = cur.fetchone()
                if row:
                    action_type, action_data = row
                    
                    # Executa a ação inversa
                    self._execute_inverse_action(action_type, action_data)
                    
                    # Salva o estado
                    self._save_history_state()
                    
                    # Atualiza a interface
                    self._update_ui()
                    
                    return True
                    
            finally:
                conn.close()
                
            return False
            
        finally:
            self.action_in_progress = False
    
    def redo(self):
        """Refaz a próxima ação"""
        if self.action_in_progress or not self.current_image_id or self.current_position >= self.max_position:
            return False
            
        self.action_in_progress = True
        
        try:
            # Obtém a ação a ser refeita
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """SELECT action_type, action_data 
                       FROM history_actions 
                       WHERE image_id = ? 
                       ORDER BY timestamp ASC 
                       LIMIT 1 OFFSET ?""",
                    (self.current_image_id, self.current_position)
                )
                
                row = cur.fetchone()
                if row:
                    action_type, action_data = row
                    
                    # Executa a ação
                    self._execute_action(action_type, action_data)
                    
                    # Incrementa a posição atual
                    self.current_position += 1
                    
                    # Salva o estado
                    self._save_history_state()
                    
                    # Atualiza a interface
                    self._update_ui()
                    
                    return True
                    
            finally:
                conn.close()
                
            return False
            
        finally:
            self.action_in_progress = False
    
    def _execute_action(self, action_type, action_data):
        """Executa uma ação do histórico"""
        # Implementar a lógica para executar diferentes tipos de ações
        if action_data and isinstance(action_data, bytes):
            try:
                data = json.loads(action_data.decode('utf-8'))
            except:
                data = action_data
        else:
            data = action_data
            
        # Exemplo de implementação para diferentes tipos de ações
        if action_type == 'filter':
            # Aplica o filtro novamente
            filter_name = data.get('name')
            params = data.get('params', {})
            self.app.apply_filter(filter_name, **params)
            
        elif action_type == 'crop':
            # Aplica o corte
            x, y, width, height = data.get('x'), data.get('y'), data.get('width'), data.get('height')
            self.app.crop_image(x, y, width, height)
            
        elif action_type == 'resize':
            # Redimensiona a imagem
            width, height = data.get('width'), data.get('height')
            self.app.resize_image(width, height)
            
        elif action_type == 'rotate':
            # Rotaciona a imagem
            angle = data.get('angle')
            self.app.rotate_image(angle)
            
        elif action_type == 'flip':
            # Espelha a imagem
            direction = data.get('direction')
            self.app.flip_image(direction)
            
        elif action_type == 'restore_point':
            # Restaura a partir de um ponto de restauração
            self._restore_from_data(data)
    
    def _execute_inverse_action(self, action_type, action_data):
        """Executa a ação inversa para desfazer"""
        # Implementar a lógica para desfazer diferentes tipos de ações
        if action_data and isinstance(action_data, bytes):
            try:
                data = json.loads(action_data.decode('utf-8'))
            except:
                data = action_data
        else:
            data = action_data
            
        # Exemplo de implementação para diferentes tipos de ações
        if action_type == 'filter':
            # Restaura a imagem antes do filtro
            self._restore_previous_state()
            
        elif action_type == 'crop':
            # Restaura a imagem antes do corte
            self._restore_previous_state()
            
        elif action_type == 'resize':
            # Restaura a imagem antes do redimensionamento
            self._restore_previous_state()
            
        elif action_type == 'rotate':
            # Restaura a imagem antes da rotação
            self._restore_previous_state()
            
        elif action_type == 'flip':
            # Restaura a imagem antes do espelhamento
            self._restore_previous_state()
            
        elif action_type == 'restore_point':
            # Restaura a imagem antes da restauração
            self._restore_previous_state()
    
    def _restore_previous_state(self):
        """Restaura o estado anterior da imagem"""
        # Obtém o estado anterior
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            
            # Procura pelo ponto de restauração mais recente antes da posição atual
            cur.execute(
                """SELECT image_data FROM restoration_points 
                   WHERE image_id = ? AND id <= ? 
                   ORDER BY id DESC LIMIT 1""",
                (self.current_image_id, self.current_position)
            )
            
            row = cur.fetchone()
            if row:
                image_data = row[0]
                self._restore_from_data(image_data)
                
        finally:
            conn.close()
    
    def _restore_from_data(self, image_data):
        """Restaura a imagem a partir dos dados binários"""
        if isinstance(image_data, bytes):
            # Carrega a imagem a partir dos dados binários
            img = Image.open(io.BytesIO(image_data))
            
            # Atualiza a imagem na aplicação
            self.app.loaded_image = img
            self.app.display_image()
            self.app.image_modified = True
    
    def create_restoration_point(self, name=None, description=None):
        """
        Cria um ponto de restauração para a imagem atual.
        
        Args:
            name: Nome do ponto de restauração
            description: Descrição do ponto de restauração
        """
        if not self.current_image_id or not self.app.loaded_image:
            return False
            
        # Gera um nome padrão se não for fornecido
        if not name:
            name = f"Ponto de Restauração {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
        # Converte a imagem para bytes
        img_bytes = io.BytesIO()
        self.app.loaded_image.save(img_bytes, format=self.app.loaded_image.format or 'PNG')
        img_data = img_bytes.getvalue()
        
        # Salva o ponto de restauração no banco de dados
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO restoration_points (image_id, name, image_data, description) VALUES (?, ?, ?, ?)",
                (self.current_image_id, name, img_data, description)
            )
            conn.commit()
            
            # Adiciona uma ação ao histórico
            self.add_action('restore_point', {'name': name}, f"Ponto de restauração: {name}")
            
            return True
            
        finally:
            conn.close()
    
    def get_restoration_points(self):
        """Obtém a lista de pontos de restauração para a imagem atual"""
        if not self.current_image_id:
            return []
            
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, name, timestamp, description 
                   FROM restoration_points 
                   WHERE image_id = ? 
                   ORDER BY timestamp DESC""",
                (self.current_image_id,)
            )
            
            return [
                {
                    'id': row[0],
                    'name': row[1],
                    'timestamp': row[2],
                    'description': row[3]
                }
                for row in cur.fetchall()
            ]
            
        finally:
            conn.close()
    
    def restore_point(self, point_id):
        """
        Restaura a imagem para um ponto de restauração específico.
        
        Args:
            point_id: ID do ponto de restauração
        """
        if not self.current_image_id:
            return False
            
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT image_data, name FROM restoration_points WHERE id = ? AND image_id = ?",
                (point_id, self.current_image_id)
            )
            
            row = cur.fetchone()
            if row:
                image_data, name = row
                
                # Restaura a imagem
                self._restore_from_data(image_data)
                
                # Adiciona uma ação ao histórico
                self.add_action('restore_point', image_data, f"Restaurado para: {name}")
                
                return True
                
            return False
            
        finally:
            conn.close()
    
    def show_history_window(self):
        """Exibe a janela de histórico"""
        import customtkinter as ctk
        from tkinter import ttk
        
        # Se a janela já estiver aberta, apenas a traz para frente
        if self.history_window and self.history_window.winfo_exists():
            self.history_window.lift()
            self.history_window.focus_force()
            return
            
        # Cria a janela
        self.history_window = ctk.CTkToplevel(self.app)
        self.history_window.title("Histórico de Edições")
        self.history_window.geometry("600x500")
        self.history_window.resizable(True, True)
        
        # Cria o notebook para abas
        notebook = ttk.Notebook(self.history_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Aba de ações
        actions_frame = ctk.CTkFrame(notebook)
        notebook.add(actions_frame, text="Ações")
        
        # Aba de pontos de restauração
        restore_frame = ctk.CTkFrame(notebook)
        notebook.add(restore_frame, text="Pontos de Restauração")
        
        # Preenche a aba de ações
        self._create_actions_tab(actions_frame)
        
        # Preenche a aba de pontos de restauração
        self._create_restore_points_tab(restore_frame)
    
    def _create_actions_tab(self, parent):
        """Cria a interface da aba de ações"""
        # Frame para os botões
        buttons_frame = ctk.CTkFrame(parent)
        buttons_frame.pack(fill="x", padx=10, pady=5)
        
        # Botões de desfazer/refazer
        undo_button = ctk.CTkButton(
            buttons_frame,
            text="↩️ Desfazer12",
            command=self.undo
        )
        undo_button.pack(side="left", padx=5)
        
        redo_button = ctk.CTkButton(
            buttons_frame,
            text="↪️ Refazer",
            command=self.redo
        )
        redo_button.pack(side="left", padx=5)
        
        # Frame para a lista de ações
        list_frame = ctk.CTkFrame(parent)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Lista de ações
        self.actions_list = ttk.Treeview(
            list_frame,
            columns=("timestamp", "description"),
            show="headings"
        )
        self.actions_list.heading("timestamp", text="Data/Hora")
        self.actions_list.heading("description", text="Descrição")
        self.actions_list.column("timestamp", width=150)
        self.actions_list.column("description", width=400)
        self.actions_list.pack(fill="both", expand=True, side="left")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.actions_list.yview)
        scrollbar.pack(fill="y", side="right")
        self.actions_list.configure(yscrollcommand=scrollbar.set)
        
        # Preenche a lista de ações
        self._populate_actions_list()
        
        # Bind para selecionar uma ação
        self.actions_list.bind("<<TreeviewSelect>>", self._on_action_selected)
    
    def _create_restore_points_tab(self, parent):
        """Cria a interface da aba de pontos de restauração"""
        # Frame para os botões
        buttons_frame = ctk.CTkFrame(parent)
        buttons_frame.pack(fill="x", padx=10, pady=5)
        
        # Botão para criar ponto de restauração
        create_button = ctk.CTkButton(
            buttons_frame,
            text="➕ Criar Ponto de Restauração",
            command=self._show_create_restore_point_dialog
        )
        create_button.pack(side="left", padx=5)
        
        # Botão para restaurar
        restore_button = ctk.CTkButton(
            buttons_frame,
            text="🔄 Restaurar Selecionado",
            command=self._restore_selected_point
        )
        restore_button.pack(side="left", padx=5)
        
        # Frame para a lista de pontos
        list_frame = ctk.CTkFrame(parent)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Lista de pontos de restauração
        self.restore_points_list = ttk.Treeview(
            list_frame,
            columns=("name", "timestamp", "description"),
            show="headings"
        )
        self.restore_points_list.heading("name", text="Nome")
        self.restore_points_list.heading("timestamp", text="Data/Hora")
        self.restore_points_list.heading("description", text="Descrição")
        self.restore_points_list.column("name", width=150)
        self.restore_points_list.column("timestamp", width=150)
        self.restore_points_list.column("description", width=250)
        self.restore_points_list.pack(fill="both", expand=True, side="left")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.restore_points_list.yview)
        scrollbar.pack(fill="y", side="right")
        self.restore_points_list.configure(yscrollcommand=scrollbar.set)
        
        # Preenche a lista de pontos de restauração
        self._populate_restore_points_list()
    
    def _populate_actions_list(self):
        """Preenche a lista de ações"""
        # Limpa a lista
        for item in self.actions_list.get_children():
            self.actions_list.delete(item)
            
        if not self.current_image_id:
            return
            
        # Obtém as ações do banco de dados
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, timestamp, action_type, description 
                   FROM history_actions 
                   WHERE image_id = ? 
                   ORDER BY timestamp DESC""",
                (self.current_image_id,)
            )
            
            for i, (id, timestamp, action_type, description) in enumerate(cur.fetchall()):
                # Formata a descrição
                if not description:
                    description = f"Ação: {action_type}"
                    
                # Adiciona à lista
                item_id = self.actions_list.insert("", "end", values=(timestamp, description))
                
                # Destaca a posição atual
                if i == self.max_position - self.current_position - 1:
                    self.actions_list.item(item_id, tags=("current",))
                    self.actions_list.tag_configure("current", background="#4a6984")
                    
        finally:
            conn.close()
    
    def _populate_restore_points_list(self):
        """Preenche a lista de pontos de restauração"""
        # Limpa a lista
        for item in self.restore_points_list.get_children():
            self.restore_points_list.delete(item)
            
        # Obtém os pontos de restauração
        restore_points = self.get_restoration_points()
        
        # Adiciona à lista
        for point in restore_points:
            self.restore_points_list.insert(
                "", "end", 
                values=(point['name'], point['timestamp'], point['description'] or ""),
                tags=(str(point['id']),)
            )
    
    def _on_action_selected(self, event):
        """Manipula a seleção de uma ação na lista"""
        # Obtém o item selecionado
        selection = self.actions_list.selection()
        if not selection:
            return
            
        # Obtém o índice do item selecionado
        index = self.actions_list.index(selection[0])
        
        # Calcula a nova posição
        new_position = self.max_position - index - 1
        
        # Se a posição for diferente da atual, navega até ela
        if new_position != self.current_position:
            # Navega para a posição selecionada
            self._navigate_to_position(new_position)
    
    def _navigate_to_position(self, position):
        """Navega para uma posição específica no histórico"""
        if position < 0 or position > self.max_position:
            return
            
        # Calcula quantos passos precisamos desfazer ou refazer
        steps = position - self.current_position
        
        if steps < 0:
            # Desfazer
            for _ in range(-steps):
                self.undo()
        elif steps > 0:
            # Refazer
            for _ in range(steps):
                self.redo()
    
    def _show_create_restore_point_dialog(self):
        """Exibe o diálogo para criar um ponto de restauração"""
        import customtkinter as ctk
        
        dialog = ctk.CTkToplevel(self.history_window)
        dialog.title("Criar Ponto de Restauração")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self.history_window)
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
        fields_frame = ctk.CT
        fields_frame = ctk.CTkFrame(main_frame, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
        fields_frame.pack(fill="x", pady=10)

# Campo para nome
        name_label = ctk.CTkLabel(
            fields_frame,
            text="Nome:",
            font=("Arial", 12),
            text_color=THUMB_TEXT_COLOR
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
            font=("Arial", 12),
            text_color=THUMB_TEXT_COLOR
        )
        desc_label.pack(anchor="w")
        
        desc_entry = ctk.CTkEntry(
            fields_frame,
            width=380,
            placeholder_text="Descrição opcional"
        )
        desc_entry.pack(fill="x")
        
        # Botões
        buttons_frame = ctk.CTkFrame(dialog, fg_color=THUMB_WINDOW_BACKGROUND_COLOR)
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
    if not name:
        messagebox.showwarning("Aviso", "Por favor, forneça um nome para o ponto de restauração.")
        return
        
    # Cria o ponto de restauração
    success = self.create_restoration_point(name, description)
    
    if success:
        # Fecha o diálogo
        dialog.destroy()
        
        # Atualiza a lista
        self._populate_restore_points_list()
        
        # Exibe mensagem de sucesso
        messagebox.showinfo("Sucesso", f"Ponto de restauração '{name}' criado com sucesso!")
    else:
        messagebox.showerror("Erro", "Não foi possível criar o ponto de restauração.")

def _restore_selected_point(self):
    """Restaura o ponto de restauração selecionado na lista"""
    # Obtém o item selecionado
    selection = self.restore_points_list.selection()
    if not selection:
        messagebox.showwarning("Aviso", "Por favor, selecione um ponto de restauração.")
        return

    # Obtém o ID do ponto de restauração
    item_id = self.restore_points_list.item(selection[0], "tags")[0]
    
    # Obtém o nome do ponto para confirmação
    point_name = self.restore_points_list.item(selection[0], "values")[0]

    # Restaura o ponto
    self.restore_point(int(item_id))
    
    # Confirma a restauração
    confirm = messagebox.askyesno(
        "Confirmar Restauração",
        f"Tem certeza que deseja restaurar para o ponto '{point_name}'?\n\n"
        "Todas as alterações não salvas serão perdidas."
    )
    
    if confirm:
        # Restaura o ponto
        success = self.restore_point(int(item_id))
        
        if success:
            messagebox.showinfo("Sucesso", f"Imagem restaurada para o ponto '{point_name}'.")
            
            # Fecha a janela de histórico
            if self.history_window:
                self.history_window.destroy()
        else:
            messagebox.showerror("Erro", "Não foi possível restaurar o ponto selecionado.")

def _update_ui(self):
    """Atualiza a interface do usuário com base no estado atual do histórico"""
    # Atualiza os botões de desfazer/refazer na aplicação principal
    if hasattr(self.app, 'undo_button'):
        self.app.undo_button.configure(state="normal" if self.current_position > 0 else "disabled")
        
    if hasattr(self.app, 'redo_button'):
        self.app.redo_button.configure(state="normal" if self.current_position < self.max_position else "disabled")
        
    # Atualiza a lista de ações se a janela de histórico estiver aberta
    if self.history_window and self.history_window.winfo_exists():
        self._populate_actions_list()