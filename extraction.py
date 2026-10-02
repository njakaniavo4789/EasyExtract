import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import time
import threading
import random

# --- Configuration de l'apparence globale ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ModernExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuration de la fenêtre
        self.title("NexusExtract AI - Immersive Data Scraper")
        self.geometry("1100x700")
        self.configure(fg_color="#0a0a0a")  # Noir profond
        
        # Couleurs personnalisées (Palette Néon)
        self.colors = {
            "bg_main": "#0a0a0a",
            "bg_sidebar": "#121212",
            "bg_card": "#1e1e1e",
            "accent_primary": "#00f0ff",  # Cyan Néon
            "accent_secondary": "#7000ff", # Violet Profond
            "text_main": "#ffffff",
            "text_sub": "#888888",
            "success": "#00ff88"
        }

        # Variables
        self.files_to_process = []
        self.is_processing = False

        # Layout Grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 1. SIDEBAR (Navigation Immersive) ---
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=self.colors["bg_sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1) # Spacer

        # Logo
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="NEXUS\nEXTRACT", 
            font=ctk.CTkFont(size=28, weight="bold", family="Orbitron"), # Police futuriste si dispo, sinon fallback
            text_color=self.colors["accent_primary"],
            justify="left"
        )
        self.logo_label.grid(row=0, column=0, padx=30, pady=(40, 40), sticky="w")

        # Boutons de navigation personnalisés (Hover effect)
        self.create_nav_button("Dashboard", "🏠", 1)
        self.create_nav_button("Historique", "🕓", 2)
        self.create_nav_button("Paramètres", "⚙️", 3)
        
        # Status du système en bas de la sidebar
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.status_frame.grid(row=7, column=0, padx=20, pady=20, sticky="ew")
        
        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", text_color=self.colors["success"], font=("Arial", 16))
        self.status_dot.pack(side="left")
        self.status_label = ctk.CTkLabel(self.status_frame, text="Système en ligne", text_color=self.colors["text_sub"], font=("Arial", 12))
        self.status_label.pack(side="left", padx=5)

        # --- 2. ZONE PRINCIPALE (Header + Workspace) ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Header
        self.header = ctk.CTkFrame(self.main_container, fg_color="transparent", height=50)
        self.header.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        self.page_title = ctk.CTkLabel(self.header, text="Extraction de Données", font=ctk.CTkFont(size=24, weight="bold"))
        self.page_title.pack(side="left")

        # Barre de recherche fictive
        self.search_bar = ctk.CTkEntry(
            self.header, 
            placeholder_text="Rechercher un modèle...", 
            width=200, 
            corner_radius=20,
            border_color=self.colors["bg_card"],
            fg_color=self.colors["bg_card"]
        )
        self.search_bar.pack(side="right", padx=10)

        # --- 3. WORKSPACE (Drop Zone + Logs) ---
        self.workspace = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.workspace.grid(row=1, column=0, sticky="nsew")
        self.workspace.grid_columnconfigure(0, weight=2) # Zone de drop plus large
        self.workspace.grid_columnconfigure(1, weight=1) # Logs
        self.workspace.grid_rowconfigure(0, weight=1)

        # A. Zone de Drop "Glassmorphism"
        self.drop_zone = ctk.CTkFrame(
            self.workspace, 
            corner_radius=20, 
            fg_color="#151515", 
            border_width=1, 
            border_color="#333"
        )
        self.drop_zone.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        # Contenu central de la drop zone
        self.drop_content = ctk.CTkFrame(self.drop_zone, fg_color="transparent")
        self.drop_content.place(relx=0.5, rely=0.5, anchor="center")

        self.icon_label = ctk.CTkLabel(self.drop_content, text="☁️", font=("Segoe UI Emoji", 60), text_color=self.colors["accent_primary"])
        self.icon_label.pack(pady=10)

        self.drop_text = ctk.CTkLabel(
            self.drop_content, 
            text="Glissez vos fichiers CSV ou Images ici", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.drop_text.pack()

        self.browse_btn = ctk.CTkButton(
            self.drop_content, 
            text="Parcourir les fichiers", 
            command=self.browse_files,
            fg_color=self.colors["accent_secondary"],
            hover_color="#5a00cc",
            corner_radius=8,
            height=40
        )
        self.browse_btn.pack(pady=20)

        # B. Panneau de Logs (Console d'extraction)
        self.log_panel = ctk.CTkFrame(self.workspace, corner_radius=20, fg_color=self.colors["bg_card"])
        self.log_panel.grid(row=0, column=1, sticky="nsew")
        
        self.log_title = ctk.CTkLabel(self.log_panel, text="Console d'Extraction", font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        self.log_title.pack(fill="x", padx=20, pady=(20, 10))

        self.log_box = ctk.CTkTextbox(
            self.log_panel, 
            fg_color="#0f0f0f", 
            text_color="#00ff88", 
            font=("Consolas", 12),
            corner_radius=10
        )
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_box.insert("0.0", "> Système initialisé...\n> En attente de fichiers...\n")

        # --- 4. BOUTON D'ACTION FLOTTANT (Bas droite) ---
        self.action_btn = ctk.CTkButton(
            self, 
            text="LANCER L'EXTRACTION", 
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=self.colors["accent_primary"],
            text_color="black",
            hover_color="#00c0cc",
            height=50,
            width=200,
            corner_radius=25,
            command=self.start_extraction_thread
        )
        # On le place par rapport à la fenêtre principale, pas au grid, pour un effet flottant
        self.action_btn.place(relx=0.95, rely=0.95, anchor="se")

        # Barre de progression (cachée au début, apparaît en bas)
        self.progress_bar = ctk.CTkProgressBar(self.main_container, height=4, corner_radius=0, progress_color=self.colors["accent_primary"])
        self.progress_bar.set(0)
        # On ne l'affiche pas tout de suite

    def create_nav_button(self, text, icon, row):
        btn = ctk.CTkButton(
            self.sidebar,
            text=f"  {icon}  {text}",
            anchor="w",
            fg_color="transparent",
            text_color=self.colors["text_sub"],
            hover_color="#1f1f1f",
            height=45,
            corner_radius=10,
            font=ctk.CTkFont(size=14)
        )
        btn.grid(row=row, column=0, padx=15, pady=5, sticky="ew")
        
        # Effet de survol pour changer la couleur du texte
        btn.bind("<Enter>", lambda e: btn.configure(text_color=self.colors["text_main"]))
        btn.bind("<Leave>", lambda e: btn.configure(text_color=self.colors["text_sub"]))

    def log(self, message):
        """Ajoute un message à la console avec timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")

    def browse_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Data Files", "*.csv *.xlsx *.json"), ("Images", "*.png *.jpg *.jpeg")])
        if files:
            self.files_to_process = files
            self.log(f"{len(files)} fichier(s) sélectionné(s).")
            self.drop_text.configure(text=f"{len(files)} fichiers prêts", text_color=self.colors["success"])
            self.icon_label.configure(text="📂", text_color=self.colors["success"])

    def start_extraction_thread(self):
        if self.is_processing:
            return
        if not self.files_to_process:
            self.log("⚠️ Aucun fichier à traiter. Veuillez en sélectionner.")
            return

        self.is_processing = True
        self.action_btn.configure(state="disabled", text="TRAITEMENT...")
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.progress_bar.set(0)
        
        # Lancement du thread pour ne pas bloquer l'UI
        threading.Thread(target=self.process_data, daemon=True).start()

    def process_data(self):
        """Simulation d'un processus d'extraction IA complexe"""
        self.log("🚀 Initialisation du moteur d'extraction Nexus...")
        time.sleep(1)
        self.log("🧠 Chargement des modèles de vision par ordinateur...")
        
        total_files = len(self.files_to_process)
        
        for i, file in enumerate(self.files_to_process):
            filename = file.split("/")[-1]
            self.log(f"📄 Analyse de : {filename}")
            
            # Simulation d'étapes
            steps = ["Lecture des métadonnées", "Détection d'objets", "Extraction OCR", "Nettoyage des données", "Sauvegarde JSON"]
            for step in steps:
                time.sleep(random.uniform(0.1, 0.4))
                self.log(f"   > {step}... OK")
            
            # Mise à jour de la barre de progression
            progress = (i + 1) / total_files
            self.progress_bar.set(progress)
            
        self.log("✅ EXTRACTION TERMINÉE AVEC SUCCÈS.")
        self.log(f"📊 {total_files} fichiers traités. Données prêtes.")
        
        # Reset UI
        self.is_processing = False
        self.action_btn.configure(state="normal", text="LANCER L'EXTRACTION")
        self.drop_text.configure(text="Glissez vos fichiers CSV ou Images ici", text_color="white")
        self.icon_label.configure(text="☁️", text_color=self.colors["accent_primary"])
        self.files_to_process = []

if __name__ == "__main__":
    app = ModernExtractorApp()
    app.mainloop()