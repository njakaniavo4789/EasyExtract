import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import time
import threading
import math
import json
import os
import subprocess
import sys
from queue import Queue, Empty
from datetime import datetime

# --- Extraction PDF ---
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# --- Gestion du son ---
try:
    import winsound
    def play_sound(sound_type):
        if sound_type == "click": winsound.Beep(800, 50)
        elif sound_type == "success": winsound.Beep(1200, 150)
        elif sound_type == "error": winsound.Beep(300, 200)
except ImportError:
    def play_sound(sound_type): pass

ctk.set_appearance_mode("Dark")


# ═══════════════════════════════════════════════════════
# 🔧 FONCTION UTILITAIRE : OUVERTURE DE DOSSIER MULTI-PLATEFORME
# ═══════════════════════════════════════════════════════
def open_folder_system(path, select_file=None, parent_window=None):
    """
    Ouvre un dossier dans l'explorateur système.
    Si select_file est fourni, le fichier est sélectionné/surligné.
    Retourne (success: bool, error_message: str)
    """
    # Normaliser le chemin
    path = os.path.normpath(path)
    
    # Créer le dossier s'il n'existe pas
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            return False, f"Impossible de créer le dossier :\n{path}\n\n{e}"
    
    # Si un fichier spécifique doit être sélectionné
    if select_file:
        select_file = os.path.normpath(select_file)
        if not os.path.exists(select_file):
            select_file = None
    
    try:
        if sys.platform == "win32":  # Windows
            if select_file:
                # Ouvre l'explorateur ET sélectionne le fichier
                # Note : shell=True est important pour /select
                subprocess.Popen(f'explorer /select,"{select_file}"', shell=True)
            else:
                # Ouvre juste le dossier
                subprocess.Popen(f'explorer "{path}"', shell=True)
            return True, ""
        
        elif sys.platform == "darwin":  # macOS
            if select_file:
                subprocess.Popen(["open", "-R", select_file])
            else:
                subprocess.Popen(["open", path])
            return True, ""
        
        else:  # Linux
            subprocess.Popen(["xdg-open", path])
            return True, ""
    
    except Exception as e:
        # Fallback : essayer avec os.startfile (Windows uniquement)
        if sys.platform == "win32":
            try:
                os.startfile(path)
                return True, ""
            except Exception as e2:
                return False, f"Erreur d'ouverture :\n{e2}"
        return False, f"Erreur d'ouverture :\n{e}"


# ═══════════════════════════════════════════════════════
# 🎉 FENÊTRE DE SUCCÈS ANIMÉE
# ═══════════════════════════════════════════════════════
class SuccessWindow(ctk.CTkToplevel):
    def __init__(self, parent, stats, output_dir, colors):
        super().__init__(parent)
        self.parent = parent
        self.output_dir = output_dir
        self.colors = colors
        self.animation_step = 0
        self.circle_radius = 0
        self.max_radius = 35
        
        self.title("Extraction Terminée")
        self.geometry("480x600")
        self.resizable(False, False)
        self.configure(fg_color="#0a0a0a")
        
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        parent.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - 480) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{px}+{py}")
        
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        
        # Canvas pour l'animation du cercle
        self.canvas = tk.Canvas(self, width=120, height=120, bg="#0a0a0a", highlightthickness=0)
        self.canvas.pack(pady=(30, 10))
        
        ctk.CTkLabel(self, text="EXTRACTION RÉUSSIE",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=colors["accent_primary"]).pack(pady=(5, 5))
        
        ctk.CTkLabel(self, text=f"{stats['pdfs']} PDF convertis en JSON",
                     font=ctk.CTkFont(size=13),
                     text_color=colors["text_sub"]).pack(pady=(0, 20))
        
        # Carte des statistiques
        stats_frame = ctk.CTkFrame(self, fg_color=colors["bg_card"], corner_radius=15,
                                    border_width=1, border_color="#1f1f1f")
        stats_frame.pack(fill="x", padx=35, pady=(0, 20))
        
        stats_grid = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_grid.pack(padx=20, pady=20, fill="x")
        stats_grid.grid_columnconfigure((0, 1), weight=1)
        
        self.create_stat_box(stats_grid, "📄", f"{stats['pages']:,}", "Pages", 0, 0)
        self.create_stat_box(stats_grid, "⏱️", f"{stats['time']:.1f}s", "Durée", 0, 1)
        self.create_stat_box(stats_grid, "📊", f"{stats['words']:,}", "Mots", 1, 0)
        self.create_stat_box(stats_grid, "⚡",
                             f"{stats['pages']/stats['time']:.0f}/s" if stats['time'] > 0 else "—",
                             "Vitesse", 1, 1)
        
        # Chemin du dossier
        ctk.CTkLabel(self, text="DOSSIER DE SORTIE",
                     font=("Consolas", 10, "bold"),
                     text_color=colors["text_sub"]).pack(anchor="w", padx=40, pady=(5, 5))
        
        path_frame = ctk.CTkFrame(self, fg_color="#050505", corner_radius=10,
                                   border_width=1, border_color="#1f1f1f")
        path_frame.pack(fill="x", padx=35, pady=(0, 25))
        
        # Champ de texte éditable (pas readonly pour pouvoir copier facilement)
        self.path_var = tk.StringVar(value=output_dir)
        self.path_entry = ctk.CTkEntry(
            path_frame,
            textvariable=self.path_var,
            fg_color="transparent",
            border_width=0,
            font=("Consolas", 10),
            text_color=colors["text_sub"]
        )
        self.path_entry.pack(fill="x", padx=15, pady=12)
        
        # Boutons d'action
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=35, pady=(0, 30))
        
        # Bouton principal : Ouvrir le dossier
        self.open_folder_btn = ctk.CTkButton(
            btn_frame,
            text="📁   OUVRIR LE DOSSIER JSON",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=colors["accent_primary"],
            text_color="black",
            hover_color="#00c0cc",
            height=50,
            corner_radius=25,
            command=self.open_folder
        )
        self.open_folder_btn.pack(fill="x", pady=(0, 8))
        
        # Bouton secondaire : Copier le chemin
        self.copy_btn = ctk.CTkButton(
            btn_frame,
            text="📋  Copier le chemin",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color=colors["text_sub"],
            hover_color="#151515",
            border_width=1,
            border_color="#1f1f1f",
            height=38,
            corner_radius=19,
            command=self.copy_path
        )
        self.copy_btn.pack(fill="x", pady=(0, 8))
        
        # Bouton fermer
        self.close_btn = ctk.CTkButton(
            btn_frame,
            text="Fermer",
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            text_color=colors["text_sub"],
            hover_color="#151515",
            height=35,
            corner_radius=17,
            command=self.close_window
        )
        self.close_btn.pack(fill="x")
        
        self.animate_circle()
        self.fade_in()
    
    def create_stat_box(self, parent, icon, value, label, row, col):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        
        ctk.CTkLabel(box, text=icon, font=("Segoe UI Emoji", 18)).pack()
        ctk.CTkLabel(box, text=value, font=("Consolas", 16, "bold"),
                     text_color=self.colors["accent_primary"]).pack()
        ctk.CTkLabel(box, text=label, font=("Consolas", 9),
                     text_color=self.colors["text_sub"]).pack()
    
    def animate_circle(self):
        if self.circle_radius < self.max_radius:
            self.circle_radius += 3
            self.canvas.delete("all")
            
            pulse = int(abs(math.sin(self.animation_step / 15)) * 10) + 50
            self.canvas.create_oval(
                60 - pulse, 60 - pulse, 60 + pulse, 60 + pulse,
                outline="#1f1f1f", width=2, fill=""
            )
            
            self.canvas.create_arc(
                60 - self.max_radius, 60 - self.max_radius,
                60 + self.max_radius, 60 + self.max_radius,
                start=90, extent=-self.circle_radius * (360 / self.max_radius),
                outline=self.colors["success"], width=4, style="arc"
            )
            
            self.canvas.create_oval(
                60 - self.circle_radius + 5, 60 - self.circle_radius + 5,
                60 + self.circle_radius - 5, 60 + self.circle_radius - 5,
                fill="#0a1a1a", outline=""
            )
            
            self.animation_step += 1
            self.after(30, self.animate_circle)
        else:
            self.canvas.delete("all")
            self.canvas.create_oval(25, 25, 95, 95,
                outline=self.colors["success"], width=4, fill="#0a1a1a")
            self.canvas.create_line(45, 62, 56, 73, 
                fill=self.colors["success"], width=4, capstyle="round")
            self.canvas.create_line(56, 73, 78, 48, 
                fill=self.colors["success"], width=4, capstyle="round")
    
    def fade_in(self):
        try:
            current = float(self.attributes("-alpha"))
            if current < 1.0:
                self.attributes("-alpha", min(1.0, current + 0.08))
                self.after(20, self.fade_in)
        except:
            self.attributes("-alpha", 1.0)
    
    def find_latest_json(self):
        """Trouve le fichier JSON le plus récent dans le dossier de sortie"""
        if not os.path.exists(self.output_dir):
            return None
        
        try:
            json_files = [f for f in os.listdir(self.output_dir) if f.endswith('.json')]
            if not json_files:
                return None
            
            full_paths = [os.path.join(self.output_dir, f) for f in json_files]
            return max(full_paths, key=os.path.getmtime)
        except Exception:
            return None
    
    def open_folder(self):
        """Ouvre le dossier avec le dernier JSON sélectionné"""
        play_sound("click")
        
        # Trouver le dernier JSON
        latest_json = self.find_latest_json()
        
        # Ouvrir avec sélection du fichier
        success, error = open_folder_system(
            self.output_dir, 
            select_file=latest_json,
            parent_window=self
        )
        
        if not success:
            # Fallback : proposer de copier le chemin
            response = messagebox.askyesno(
                "Erreur d'ouverture",
                f"{error}\n\n"
                f"Voulez-vous copier le chemin dans le presse-papiers ?\n\n"
                f"Chemin : {self.output_dir}"
            )
            if response:
                self.copy_path()
    
    def copy_path(self):
        """Copie le chemin dans le presse-papiers"""
        play_sound("click")
        try:
            self.clipboard_clear()
            self.clipboard_append(self.output_dir)
            self.update()
            
            # Feedback visuel
            original_text = self.copy_btn.cget("text")
            self.copy_btn.configure(text="✅  Chemin copié !", text_color=self.colors["success"])
            self.after(2000, lambda: self.copy_btn.configure(
                text=original_text, text_color=self.colors["text_sub"]
            ))
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de copier :\n{e}")
    
    def close_window(self):
        play_sound("click")
        try:
            self.grab_release()
        except:
            pass
        self.destroy()


class AnimatedBackground(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(bg="#050505", highlightthickness=0)
        self.grid_spacing = 40
        self.offset = 0
        self.animate()

    def animate(self):
        self.delete("grid")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            self.after(50, self.animate)
            return
        self.offset = (self.offset + 1) % self.grid_spacing
        for x in range(0, w, self.grid_spacing):
            self.create_line(x, 0, x, h, fill="#111111", tags="grid")
        for y in range(-self.grid_spacing + self.offset, h, self.grid_spacing):
            self.create_line(0, y, w, y, fill="#111111", tags="grid")
        self.after(50, self.animate)


class ModernExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("NexusExtract AI - PDF to JSON Turbo")
        
        W, H = 1000, 640
        self.geometry(f"{W}x{H}")
        self.resizable(False, False)
        
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.configure(fg_color="#050505")
        
        self.colors = {
            "bg_sidebar": "#0a0a0a", "bg_card": "#121212",
            "accent_primary": "#00f0ff", "accent_secondary": "#7000ff",
            "text_sub": "#666666", "success": "#00ff88", "danger": "#ff0055"
        }

        self.files_to_process = []
        self.is_processing = False
        self.pulse_state = 0
        self.scan_position = 0
        self.queue = Queue()
        self.output_dir = os.path.join(os.path.expanduser("~"), "Documents", "NexusExtract_Output")
        
        # Créer le dossier au démarrage
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception as e:
            print(f"Warning: Impossible de créer {self.output_dir}: {e}")
            # Fallback sur le dossier du script
            self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Output")
            os.makedirs(self.output_dir, exist_ok=True)
        
        self.session_stats = {"pdfs": 0, "pages": 0, "words": 0, "time": 0}

        # Arrière-plan
        self.bg_canvas = AnimatedBackground(self)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # SIDEBAR
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=self.colors["bg_sidebar"])
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.logo_frame.pack(padx=25, pady=(40, 40), anchor="w")
        ctk.CTkLabel(self.logo_frame, text="NEXUS\nEXTRACT", 
                     font=ctk.CTkFont(size=26, weight="bold", family="Consolas"),
                     text_color=self.colors["accent_primary"], justify="left").pack(anchor="w")

        self.create_nav_button("PDF → JSON", "⬡")
        self.create_nav_button("Historique", "◷")
        self.create_nav_button("Paramètres", "⚙")
        
        self.open_btn = ctk.CTkButton(self.sidebar, text="📁  OUVRIR DOSSIER", anchor="w", 
            fg_color="transparent", text_color=self.colors["text_sub"], hover_color="#151515",
            height=42, corner_radius=10, font=ctk.CTkFont(size=12), command=self.open_output_dir)
        self.open_btn.pack(fill="x", padx=15, pady=(20, 3))
        
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.status_frame.pack(side="bottom", padx=25, pady=25, fill="x")
        
        if PYMUPDF_AVAILABLE:
            ctk.CTkLabel(self.status_frame, text="● Turbo Engine: ON", 
                         text_color=self.colors["success"], 
                         font=("Consolas", 10)).pack(anchor="w")
        else:
            ctk.CTkLabel(self.status_frame, text="● Turbo Engine: OFF", 
                         text_color=self.colors["danger"], 
                         font=("Consolas", 10)).pack(anchor="w")
        
        if PDFPLUMBER_AVAILABLE:
            ctk.CTkLabel(self.status_frame, text="● Fallback: Ready", 
                         text_color=self.colors["text_sub"], 
                         font=("Consolas", 9)).pack(anchor="w")
        else:
            ctk.CTkLabel(self.status_frame, text="● Fallback: Missing", 
                         text_color=self.colors["danger"], 
                         font=("Consolas", 9)).pack(anchor="w")

        # CONTENEUR DROIT
        self.right_container = ctk.CTkFrame(self, fg_color="transparent")
        self.right_container.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        # HEADER
        self.header = ctk.CTkFrame(self.right_container, fg_color="transparent", height=60)
        self.header.pack(fill="x", pady=(0, 15))
        self.header.pack_propagate(False)

        ctk.CTkLabel(self.header, text="PDF → JSON", 
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        
        self.top_status = ctk.CTkLabel(self.header, text="[ PRÊT ]", font=("Consolas", 11), 
                                        text_color=self.colors["text_sub"])
        self.top_status.pack(side="left", padx=20)

        self.action_btn = ctk.CTkButton(
            self.header, text="▶  LANCER", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors["accent_primary"], text_color="black",
            hover_color="#00c0cc", height=40, width=160, corner_radius=20,
            command=self.start_extraction_thread
        )
        self.action_btn.pack(side="right")

        # WORKSPACE
        self.workspace = ctk.CTkFrame(self.right_container, fg_color="transparent")
        self.workspace.pack(fill="both", expand=True)

        # Panneau de Logs
        self.log_panel = ctk.CTkFrame(self.workspace, width=320, corner_radius=18, 
                                       fg_color=self.colors["bg_card"], border_width=1, border_color="#1f1f1f")
        self.log_panel.pack(side="right", fill="y", padx=(15, 0))
        self.log_panel.pack_propagate(False)

        self.log_header = ctk.CTkFrame(self.log_panel, fg_color="transparent")
        self.log_header.pack(fill="x", padx=18, pady=(18, 8))
        ctk.CTkLabel(self.log_header, text="CONSOLE", font=("Consolas", 11, "bold"), 
                     text_color=self.colors["accent_primary"]).pack(side="left")
        self.log_status = ctk.CTkLabel(self.log_header, text="● IDLE", font=("Consolas", 9), 
                                        text_color=self.colors["text_sub"])
        self.log_status.pack(side="right")

        self.log_box = ctk.CTkTextbox(self.log_panel, fg_color="#080808", text_color="#00ff88",
                                       font=("Consolas", 10), corner_radius=10, border_width=0,
                                       scrollbar_button_color="#1f1f1f")
        self.log_box.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.log_box.insert("0.0", "> Nexus PDF Extractor v2.0 TURBO\n> Moteur prêt.\n")

        # Zone de Drop
        self.drop_zone = ctk.CTkFrame(self.workspace, corner_radius=18, 
                                       fg_color="#0d0d0d", border_width=2, border_color="#1f1f1f")
        self.drop_zone.pack(side="left", fill="both", expand=True)
        self.drop_zone.pack_propagate(False)

        self.drop_content = ctk.CTkFrame(self.drop_zone, fg_color="transparent")
        self.drop_content.place(relx=0.5, rely=0.5, anchor="center")

        self.icon_label = ctk.CTkLabel(self.drop_content, text="📄", font=("Segoe UI Emoji", 55), 
                                        text_color=self.colors["accent_primary"])
        self.icon_label.pack(pady=5)
        self.drop_text = ctk.CTkLabel(self.drop_content, text="Déposez vos PDF ici", 
                                       font=ctk.CTkFont(size=15, weight="bold"))
        self.drop_text.pack()
        ctk.CTkLabel(self.drop_content, text="Extraction turbo · Milliers de pages supportées", 
                     font=ctk.CTkFont(size=11), text_color=self.colors["text_sub"]).pack(pady=(5, 15))
        
        self.browse_btn = ctk.CTkButton(self.drop_content, text="SÉLECTIONNER DES PDF", 
            command=self.browse_files, fg_color="transparent", border_width=1, 
            border_color=self.colors["accent_primary"], text_color=self.colors["accent_primary"],
            hover_color="#0a1a1a", corner_radius=8, height=38, font=ctk.CTkFont(size=11, weight="bold"))
        self.browse_btn.pack()

        # Ligne de scan
        self.scan_line = tk.Frame(self.drop_zone, bg=self.colors["accent_primary"], height=2)

        # BARRE DE PROGRESSION
        progress_width = W - 220
        self.progress_bar = ctk.CTkProgressBar(
            self, height=3, width=progress_width, corner_radius=0,
            progress_color=self.colors["accent_primary"], fg_color="#1f1f1f"
        )
        self.progress_bar.set(0)
        self.progress_bar.place(x=220, y=H-3, anchor="sw")
        self.progress_bar.lower()

        self.animate_pulse()
        self.check_queue()
        
        # Log initial pour indiquer le dossier de sortie
        self.after(500, lambda: self.log(f"📁 Dossier de sortie : {self.output_dir}"))

    def create_nav_button(self, text, icon):
        btn = ctk.CTkButton(self.sidebar, text=f"  {icon}   {text}", anchor="w", fg_color="transparent",
            text_color=self.colors["text_sub"], hover_color="#151515", height=42, 
            corner_radius=10, font=ctk.CTkFont(size=13))
        btn.pack(fill="x", padx=15, pady=3)
        btn.bind("<Enter>", lambda e: (btn.configure(text_color=self.colors["accent_primary"]), play_sound("click")))
        btn.bind("<Leave>", lambda e: btn.configure(text_color=self.colors["text_sub"]))

    def open_output_dir(self):
        """Ouvre le dossier de sortie avec le dernier JSON sélectionné"""
        play_sound("click")
        
        # Trouver le dernier JSON
        latest_json = None
        if os.path.exists(self.output_dir):
            try:
                json_files = [f for f in os.listdir(self.output_dir) if f.endswith('.json')]
                if json_files:
                    full_paths = [os.path.join(self.output_dir, f) for f in json_files]
                    latest_json = max(full_paths, key=os.path.getmtime)
            except Exception:
                pass
        
        success, error = open_folder_system(self.output_dir, select_file=latest_json)
        
        if not success:
            self.log(f"⚠️ {error}")
            # Proposer de copier le chemin
            self.clipboard_clear()
            self.clipboard_append(self.output_dir)
            self.update()
            self.log(f"📋 Chemin copié : {self.output_dir}")

    def animate_pulse(self):
        if not self.is_processing:
            self.pulse_state = (self.pulse_state + 1) % 60
            bi = int(abs(math.sin(self.pulse_state / 60 * math.pi)) * 20) + 20
            self.drop_zone.configure(border_color=f"#{bi:02x}{bi:02x}{bi:02x}")
        self.after(50, self.animate_pulse)

    def animate_scan(self):
        if self.is_processing:
            h = self.drop_zone.winfo_height()
            self.scan_position = (self.scan_position + 8) % h
            self.scan_line.place(x=0, y=self.scan_position, relwidth=1)
            self.after(15, self.animate_scan)
        else:
            self.scan_line.place_forget()

    def check_queue(self):
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "log": self.log(data)
                elif msg_type == "progress": self.progress_bar.set(data)
                elif msg_type == "done": self.on_extraction_done(data)
        except Empty:
            pass
        self.after(100, self.check_queue)

    def log(self, message):
        ts = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts}] {message}\n")
        self.log_box.see("end")
        self.log_status.configure(text="● ACTIF", text_color=self.colors["accent_primary"])
        self.after(500, lambda: self.log_status.configure(text="● IDLE", text_color=self.colors["text_sub"]))

    def browse_files(self):
        if not PYMUPDF_AVAILABLE and not PDFPLUMBER_AVAILABLE:
            self.log("⚠️ Installez PyMuPDF ou pdfplumber.")
            play_sound("error")
            return
        play_sound("click")
        files = filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")])
        if files:
            self.files_to_process = files
            total_size = sum(os.path.getsize(f) for f in files) / (1024 * 1024)
            self.log(f"{len(files)} PDF détecté(s) — {total_size:.1f} MB total")
            self.drop_text.configure(text=f"{len(files)} PDF CHARGÉS", text_color=self.colors["success"])
            self.icon_label.configure(text="📚", text_color=self.colors["success"])
            self.drop_zone.configure(border_color=self.colors["success"])
            self.top_status.configure(text="[ PRÊT ]", text_color=self.colors["success"])

    def start_extraction_thread(self):
        if self.is_processing: return
        if not PYMUPDF_AVAILABLE and not PDFPLUMBER_AVAILABLE:
            self.log("⚠️ Aucun moteur PDF disponible.")
            play_sound("error")
            return
        if not self.files_to_process:
            self.log("⚠️ Aucun PDF sélectionné.")
            play_sound("error")
            return

        self.is_processing = True
        play_sound("click")
        self.action_btn.configure(state="disabled", text="⏳  TRAITEMENT...", 
                                  fg_color=self.colors["accent_secondary"])
        
        self.progress_bar.lift()
        self.progress_bar.set(0)
        self.top_status.configure(text="[ EN COURS ]", text_color=self.colors["accent_secondary"])
        self.scan_position = 0
        self.animate_scan()
        
        self.session_stats = {"pdfs": 0, "pages": 0, "words": 0, "time": 0}
        
        threading.Thread(target=self.process_data, daemon=True).start()

    def process_data(self):
        total = len(self.files_to_process)
        self.queue.put(("log", f"🚀 Démarrage — {total} PDF à traiter"))
        
        session_start = time.time()
        
        for idx, pdf_path in enumerate(self.files_to_process):
            filename = os.path.basename(pdf_path)
            file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
            self.queue.put(("log", f"📄 {filename} ({file_size_mb:.1f} MB)"))
            
            start_time = time.time()
            
            try:
                if PYMUPDF_AVAILABLE:
                    result = self.extract_pdf_fast(pdf_path)
                else:
                    result = self.extract_pdf_standard(pdf_path)
                
                output_name = os.path.splitext(filename)[0] + ".json"
                output_path = os.path.join(self.output_dir, output_name)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                elapsed = time.time() - start_time
                pages = result['statistics']['pages']
                speed = pages / elapsed if elapsed > 0 else 0
                
                self.session_stats["pdfs"] += 1
                self.session_stats["pages"] += pages
                self.session_stats["words"] += result['statistics']['words']
                
                self.queue.put(("log", f"   ✅ {pages} pages en {elapsed:.1f}s "
                                       f"({speed:.0f} pages/s)"))
                self.queue.put(("log", f"   📊 {result['statistics']['words']:,} mots, "
                                       f"{result['statistics']['tables']} tableaux"))
                
            except Exception as e:
                self.queue.put(("log", f"   ❌ Erreur : {str(e)[:80]}"))
            
            self.queue.put(("progress", (idx + 1) / total))
        
        total_time = time.time() - session_start
        self.session_stats["time"] = total_time
        self.queue.put(("done", total))

    def extract_pdf_fast(self, pdf_path):
        data = {
            "file_info": {
                "filename": os.path.basename(pdf_path),
                "full_path": pdf_path,
                "size_bytes": os.path.getsize(pdf_path),
                "extracted_at": datetime.now().isoformat(),
                "extraction_engine": "PyMuPDF (Turbo)"
            },
            "metadata": {},
            "pages": [],
            "statistics": {}
        }
        
        all_text = []
        table_count = 0
        ocr_pages = 0
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        data["metadata"] = {
            "total_pages": total_pages,
            "pdf_metadata": doc.metadata or {},
            "is_encrypted": doc.is_encrypted
        }
        self.queue.put(("log", f"   > {total_pages} pages détectées"))
        
        BATCH_SIZE = 100
        for batch_start in range(0, total_pages, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_pages)
            
            for page_num in range(batch_start, batch_end):
                page = doc[page_num]
                text = page.get_text("text")
                
                if len(text.strip()) < 20:
                    images = page.get_images()
                    if images:
                        ocr_pages += 1
                        text = f"[PAGE SCANNÉE - {len(images)} image(s)]"
                
                page_data = {
                    "page_number": page_num + 1,
                    "width": round(page.rect.width, 2),
                    "height": round(page.rect.height, 2),
                    "text": text,
                    "tables": [],
                    "images_count": len(page.get_images())
                }
                
                if self._likely_has_table(text):
                    try:
                        tables = page.find_tables()
                        for t_idx, table in enumerate(tables, start=1):
                            rows = table.extract()
                            if not rows or len(rows) < 2:
                                continue
                            headers = [str(h).strip() if h else f"col_{i}" 
                                       for i, h in enumerate(rows[0])]
                            data_rows = []
                            for row in rows[1:]:
                                data_rows.append({
                                    headers[i]: (str(cell).strip() if cell else "")
                                    for i, cell in enumerate(row) if i < len(headers)
                                })
                            page_data["tables"].append({
                                "table_index": t_idx,
                                "headers": headers,
                                "rows": data_rows,
                                "row_count": len(data_rows)
                            })
                            table_count += 1
                    except Exception:
                        pass
                
                all_text.append(text)
                data["pages"].append(page_data)
            
            self.queue.put(("log", f"   > {batch_end}/{total_pages} pages traitées"))
        
        doc.close()
        
        full_text = " ".join(all_text)
        data["statistics"] = {
            "pages": total_pages,
            "words": len(full_text.split()),
            "characters": len(full_text),
            "tables": table_count,
            "total_pages_with_tables": sum(1 for p in data["pages"] if p["tables"]),
            "ocr_pages": ocr_pages
        }
        
        return data

    def _likely_has_table(self, text):
        if not text or len(text) < 80:
            return False
        lines = text.split('\n')
        if len(lines) < 3:
            return False
        table_like_lines = sum(1 for line in lines if '   ' in line or '\t' in line)
        return table_like_lines > max(3, len(lines) * 0.3)

    def extract_pdf_standard(self, pdf_path):
        data = {
            "file_info": {
                "filename": os.path.basename(pdf_path),
                "full_path": pdf_path,
                "size_bytes": os.path.getsize(pdf_path),
                "extracted_at": datetime.now().isoformat(),
                "extraction_engine": "pdfplumber (Standard)"
            },
            "metadata": {},
            "pages": [],
            "statistics": {}
        }
        
        all_text = []
        table_count = 0
        
        with pdfplumber.open(pdf_path) as pdf:
            data["metadata"] = {
                "total_pages": len(pdf.pages),
                "pdf_metadata": pdf.metadata or {}
            }
            
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(
                    x_tolerance=3, y_tolerance=3, layout=False,
                    x_density=7.25, y_density=13
                ) or ""
                
                page_data = {
                    "page_number": page_num,
                    "width": round(page.width, 2),
                    "height": round(page.height, 2),
                    "text": text,
                    "tables": [],
                    "images_count": len(page.images)
                }
                
                if self._likely_has_table(text):
                    try:
                        tables = page.extract_tables()
                        for t_idx, table in enumerate(tables, start=1):
                            if not table or len(table) < 2:
                                continue
                            headers = [str(h).strip() if h else f"col_{i}" 
                                       for i, h in enumerate(table[0])]
                            rows = []
                            for row in table[1:]:
                                rows.append({
                                    headers[i]: (str(cell).strip() if cell else "") 
                                    for i, cell in enumerate(row) if i < len(headers)
                                })
                            page_data["tables"].append({
                                "table_index": t_idx,
                                "headers": headers,
                                "rows": rows,
                                "row_count": len(rows)
                            })
                            table_count += 1
                    except Exception:
                        pass
                
                all_text.append(text)
                data["pages"].append(page_data)
                
                if page_num % 25 == 0 or page_num == len(pdf.pages):
                    self.queue.put(("log", f"   > Page {page_num}/{len(pdf.pages)}"))
                
                page.flush_cache()
        
        full_text = " ".join(all_text)
        data["statistics"] = {
            "pages": len(data["pages"]),
            "words": len(full_text.split()),
            "characters": len(full_text),
            "tables": table_count,
            "total_pages_with_tables": sum(1 for p in data["pages"] if p["tables"]),
            "ocr_pages": 0
        }
        
        return data

    def on_extraction_done(self, total_files):
        stats = self.session_stats
        total_time = stats["time"]
        total_pages = stats["pages"]
        avg_speed = total_pages / total_time if total_time > 0 else 0
        
        self.log(f"═══════════════════════════════════")
        self.log(f"✅ TERMINÉ : {total_files} PDF traités")
        self.log(f"⏱️  Temps total : {total_time:.1f}s")
        self.log(f"📄 Pages : {total_pages:,}  |  ⚡ {avg_speed:.0f} pages/s")
        self.log(f"📊 Mots : {stats['words']:,}")
        self.log(f"═══════════════════════════════════")
        play_sound("success")
        
        self.top_status.configure(text="[ TERMINÉ ]", text_color=self.colors["success"])
        self.action_btn.configure(state="normal", text="▶  LANCER", 
                                   fg_color=self.colors["accent_primary"])
        self.drop_text.configure(text="Déposez vos PDF ici", text_color="white")
        self.icon_label.configure(text="📄", text_color=self.colors["accent_primary"])
        self.drop_zone.configure(border_color="#1f1f1f")
        self.files_to_process = []
        self.is_processing = False
        self.scan_line.place_forget()
        self.after(2000, lambda: self.progress_bar.lower())
        
        self.after(400, lambda: self.show_success_window(stats))

    def show_success_window(self, stats):
        success_win = SuccessWindow(self, stats, self.output_dir, self.colors)
        try:
            success_win.attributes("-alpha", 0)
        except:
            pass


if __name__ == "__main__":
    app = ModernExtractorApp()
    app.mainloop()