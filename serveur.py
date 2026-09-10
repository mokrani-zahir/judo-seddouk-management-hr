#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Judo Club Seddouk — Serveur de gestion des adhérents
SQLite + HTTP, sans aucune dépendance externe.
Lancer : python serveur.py  (ou via l'EXE portable)

Base de données créée automatiquement : judo.db (dans le même dossier que l'EXE)
"""

import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

PORT = 8000
HOST = "127.0.0.1"

# ── Mise à jour (GitHub) ──
REPO = "mokrani-zahir/judo-seddouk-management-hr"
RAW_PREFIX = "https://raw.githubusercontent.com/%s/master" % REPO
VERSION_JSON_URL = RAW_PREFIX + "/version.json"
APP_VERSION = "1.1.15"


def update_json_url():
    """URL du version.json (surchargeable pour tests via la variable JCS_UPDATE_JSON_URL)."""
    return os.environ.get("JCS_UPDATE_JSON_URL") or VERSION_JSON_URL


def _fix_stdio():
    """En mode 'windowed' (EXE --noconsole), stdout/stderr n'existent pas ;
    on les redirige vers /dev/null pour que print() ne plante pas."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _msgbox(title, message):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        pass


def save_file_dialog(default_name):
    """Boîte de dialogue Windows native 'Enregistrer sous'.
    Retourne le chemin choisi, ou None si l'utilisateur annule."""
    import ctypes
    from ctypes import wintypes

    class OPENFILENAME(ctypes.Structure):
        _fields_ = [
            ("lStructSize", wintypes.DWORD),
            ("hwndOwner", wintypes.HWND),
            ("hInstance", wintypes.HINSTANCE),
            ("lpstrFilter", wintypes.LPCWSTR),
            ("lpstrCustomFilter", wintypes.LPWSTR),
            ("nMaxCustFilter", wintypes.DWORD),
            ("nFilterIndex", wintypes.DWORD),
            ("lpstrFile", wintypes.LPWSTR),
            ("nMaxFile", wintypes.DWORD),
            ("lpstrFileTitle", wintypes.LPWSTR),
            ("nMaxFileTitle", wintypes.DWORD),
            ("lpstrInitialDir", wintypes.LPCWSTR),
            ("lpstrTitle", wintypes.LPCWSTR),
            ("Flags", wintypes.DWORD),
            ("nFileOffset", wintypes.WORD),
            ("nFileExtension", wintypes.WORD),
            ("lpstrDefExt", wintypes.LPCWSTR),
            ("lCustData", wintypes.LPARAM),
            ("lpfnHook", ctypes.c_void_p),
            ("lpTemplateName", wintypes.LPCWSTR),
        ]

    buf = ctypes.create_unicode_buffer(260)
    buf.value = default_name
    ofn = OPENFILENAME()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
    ofn.lpstrFilter = "Fichier JSON (*.json)\x00*.json\x00Tous les fichiers (*.*)\x00*.*\x00\x00"
    ofn.nFilterIndex = 1
    ofn.lpstrFile = ctypes.cast(buf, ctypes.c_wchar_p)
    ofn.nMaxFile = 260
    ofn.lpstrTitle = "Enregistrer la sauvegarde"
    ofn.lpstrDefExt = "json"
    ofn.Flags = 0x2 | 0x4 | 0x80000  # OVERWRITEPROMPT | HIDEREADONLY | EXPLORER
    ok = ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn))
    if not ok:
        return None
    return buf.value


def _version_tuple(v):
    parts = []
    for p in str(v).split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_update():
    """Compare la version locale à version.json publié sur GitHub."""
    import urllib.request

    try:
        with urllib.request.urlopen(update_json_url(), timeout=8) as r:
            remote = json.loads(r.read().decode("utf-8", errors="replace"))
        latest = str(remote.get("version", "")).strip()
        exe_url = str(remote.get("exe_url") or "").strip()
        notes = str(remote.get("notes") or "").strip()
        if not latest:
            return {"current": APP_VERSION, "update_available": False, "error": "version.json invalide"}
        available = _version_tuple(latest) > _version_tuple(APP_VERSION)
        return {
            "current": APP_VERSION,
            "latest": latest,
            "update_available": available,
            "exe_url": exe_url or RAW_PREFIX + "/dist/Judo_Club_Seddouk.exe",
            "notes": notes,
        }
    except Exception as e:
        return {"current": APP_VERSION, "update_available": False, "error": str(e)}


def download_update(url):
    """Télécharge le nouvel EXE à côté de l'application (sans toucher judo.db)."""
    import urllib.request

    dest = os.path.join(APP_DIR, "Judo_Club_Seddouk.new.exe")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JudoClubSeddouk-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return {"ok": True, "size": os.path.getsize(dest)}
    except Exception as e:
        return {"error": str(e)}


def resource_path(relative):
    """Chemin vers les fichiers HTML — fonctionne en dev ET packagé (PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def data_path():
    """judo.db est placé à côté de l'EXE (ou du script) pour garder les données avec l'app."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "judo.db")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "judo.db")


DB_PATH = data_path()
APP_DIR = os.path.dirname(DB_PATH)

SCHEMA = """
CREATE TABLE IF NOT EXISTS adherents (
    id TEXT PRIMARY KEY,
    numero INTEGER NOT NULL,
    nom TEXT DEFAULT '',
    prenom TEXT DEFAULT '',
    dateNaissance TEXT DEFAULT '',
    lieuNaissance TEXT DEFAULT '',
    adresse TEXT DEFAULT '',
    niveauScolaire TEXT DEFAULT '',
    etablissement TEXT DEFAULT '',
    telephone1 TEXT DEFAULT '',
    telephone2 TEXT DEFAULT '',
    saison TEXT DEFAULT '',
    photo TEXT DEFAULT '',
    tuteurNom TEXT DEFAULT '',
    enfantAutorise TEXT DEFAULT '',
    activites TEXT DEFAULT '',
    droitNumerique TEXT DEFAULT '',
    lieuDateAutorisation TEXT DEFAULT '',
    medecinNom TEXT DEFAULT '',
    medecinExamine TEXT DEFAULT '',
    nomExamine TEXT DEFAULT '',
    prenomExamine TEXT DEFAULT '',
    ageExamine TEXT DEFAULT '',
    certificatLieu TEXT DEFAULT '',
    certificatDate TEXT DEFAULT '',
    doc_ficheRemplie INTEGER DEFAULT 0,
    doc_autorisationParentale INTEGER DEFAULT 0,
    doc_certificatMedicale INTEGER DEFAULT 0,
    doc_extraitNaissance INTEGER DEFAULT 0,
    doc_photosIdentite INTEGER DEFAULT 0,
    doc_fraisInscription INTEGER DEFAULT 0,
    remarques TEXT DEFAULT '[]',
    statut TEXT DEFAULT 'brouillon',
    dateCreation TEXT DEFAULT '',
    dateModification TEXT DEFAULT ''
);
"""

ALL_COLUMNS = [
    "id", "numero", "nom", "prenom", "dateNaissance", "lieuNaissance", "adresse",
    "niveauScolaire", "etablissement", "telephone1", "telephone2", "saison", "photo",
    "tuteurNom", "enfantAutorise", "activites", "droitNumerique", "lieuDateAutorisation",
    "medecinNom", "medecinExamine", "nomExamine", "prenomExamine", "ageExamine",
    "certificatLieu", "certificatDate",
    "doc_ficheRemplie", "doc_autorisationParentale", "doc_certificatMedicale",
    "doc_extraitNaissance", "doc_photosIdentite", "doc_fraisInscription",
    "remarques", "statut", "dateCreation", "dateModification",
]

DOC_BOOL_COLS = [
    "doc_ficheRemplie", "doc_autorisationParentale", "doc_certificatMedicale",
    "doc_extraitNaissance", "doc_photosIdentite", "doc_fraisInscription",
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def normalize(data):
    """Normalise un dictionnaire venu du frontend pour l'insertion SQLite."""
    d = {k: data.get(k, "") for k in ALL_COLUMNS}
    if d.get("id") is None:
        d["id"] = ""
    if d.get("numero") is None:
        d["numero"] = 1
    for col in DOC_BOOL_COLS:
        d[col] = 1 if d.get(col) else 0
    d["remarques"] = json.dumps(d.get("remarques") or [], ensure_ascii=False)
    return d


def row_to_dict(row):
    d = dict(row)
    for col in DOC_BOOL_COLS:
        d[col] = bool(d.get(col))
    try:
        d["remarques"] = json.loads(d.get("remarques") or "[]")
    except (ValueError, TypeError):
        d["remarques"] = []
    return d


def replace_all(adherents):
    """Remplace toute la table par la liste fournie (mode mono-utilisateur local)."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM adherents")
        placeholders = ",".join("?" for _ in ALL_COLUMNS)
        sql = "INSERT OR REPLACE INTO adherents ({}) VALUES ({})".format(
            ",".join(ALL_COLUMNS), placeholders
        )
        for a in adherents or []:
            vals = [normalize(a)[c] for c in ALL_COLUMNS]
            conn.execute(sql, vals)
        conn.commit()
    finally:
        conn.close()


def fetch_all():
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM adherents ORDER BY numero").fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 + connexion fermée après chaque réponse : idéal en local mono-utilisateur,
    # et surtout évite l'empilement de threads keep-alive qui gelait le serveur lors
    # des rafales de requêtes (démarrage de la fenêtre, impression, export).
    protocol_version = "HTTP/1.0"

    # ---------- utilitaires ----------
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except (FileNotFoundError, IsADirectoryError):
            self._send_json({"error": "Fichier introuvable"}, 404)
            return
        ext = os.path.splitext(path)[1].lower()
        ctype = "text/html; charset=utf-8"
        if ext == ".png":
            ctype = "image/png"
        elif ext == ".jpg" or ext == ".jpeg":
            ctype = "image/jpeg"
        elif ext == ".css":
            ctype = "text/css"
        elif ext == ".js":
            ctype = "application/javascript"
        elif ext == ".json":
            ctype = "application/json; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.close_connection = True
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def log_message(self, fmt, *args):
        # Journal minimal
        sys.stderr.write("[serveur] %s - %s\n" % (self.address_string(), fmt % args))

    # ---------- routage ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/"):
            self._api_get(path)
            return
        self._serve_static(path)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/adherents":
            self._api_replace()
        elif path == "/api/import":
            self._api_import()
        elif path == "/api/update/download":
            self._api_update_download()
        elif path == "/api/update/apply":
            self._api_update_apply()
        else:
            self._send_json({"error": "Not found"}, 404)

    def _serve_static(self, path):
        if path in ("/", "/index.html"):
            self._send_file(resource_path("index.html"))
        else:
            name = os.path.basename(path)
            if not name:
                self._send_json({"error": "Not found"}, 404)
                return
            full = resource_path(name)
            self._send_file(full)

    # ---------- API ----------
    def _api_get(self, path):
        if path == "/api/adherents":
            self._send_json(fetch_all())
        elif path == "/api/version":
            self._send_json({"version": APP_VERSION})
        elif path == "/api/update/check":
            self._send_json(check_update())
        elif path == "/api/export":
            body = json.dumps(fetch_all(), ensure_ascii=False).encode("utf-8")
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header(
                "Content-Disposition", 'attachment; filename="adherents_sauvegarde.json"'
            )
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _api_replace(self):
        try:
            data = json.loads(self._read_body().decode("utf-8") or "[]")
        except (ValueError, UnicodeDecodeError):
            self._send_json({"error": "JSON invalide"}, 400)
            return
        if isinstance(data, dict) and "adherents" in data:
            adherents = data["adherents"]
        elif isinstance(data, list):
            adherents = data
        else:
            self._send_json({"error": "Format invalide : liste d'adhérents attendue"}, 400)
            return
        replace_all(adherents)
        self._send_json({"ok": True, "count": len(adherents)})

    def _api_import(self):
        # Même logique que replace_all mais permet aussi l'import d'un objet {adherents:[...]}
        self._api_replace()

    def _api_update_download(self):
        info = check_update()
        if info.get("error"):
            self._send_json({"error": "Impossible de joindre le serveur de mise à jour : %s" % info["error"]})
            return
        if not info["update_available"]:
            self._send_json({"error": "Déjà à jour"})
            return
        self._send_json(download_update(info["exe_url"]))

    def _api_update_apply(self):
        if not getattr(sys, "frozen", False):
            self._send_json({"error": "L'auto-mise à jour nécessite la version portable (EXE)"}, 400)
            return
        dest = os.path.join(APP_DIR, "Judo_Club_Seddouk.new.exe")
        if not os.path.exists(dest):
            self._send_json({"error": "Fichier de mise à jour introuvable — relancez le téléchargement"}, 400)
            return
        cmd_path = os.path.join(APP_DIR, "update-install.vbs")
        script = (
            "Option Explicit\n"
            "Dim fso, dir, tries, shell, i, launched\n"
            "Set fso = CreateObject(\"Scripting.FileSystemObject\")\n"
            "Set shell = CreateObject(\"WScript.Shell\")\n"
            "dir = fso.GetParentFolderName(WScript.ScriptFullName)\n"
            "Call LogMsg(dir, \"[start] \" & Now)\n"
            "tries = 0\n"
            "Do While CheckRunning() And tries < 8\n"
            "  WScript.Sleep 1000\n"
            "  tries = tries + 1\n"
            "Loop\n"
            "If CheckRunning() Then\n"
            "  Call LogMsg(dir, \"[force] taskkill \" & Now)\n"
            "  ' PAS de /t : /t tuerait l'arborescence du process Judo, or wscript\n"
            "  ' (notre installeur) est un descendant de ce process. /im suffit : il\n"
            "  ' tue tous les process nommes Judo_Club_Seddouk.exe (parent + child).\n"
            "  shell.Run \"taskkill /f /im Judo_Club_Seddouk.exe\", 0, True\n"
            "  WScript.Sleep 2500\n"
            "  If CheckRunning() Then Call LogMsg(dir, \"[warning] encore vivant apres taskkill \" & Now)\n"
            "End If\n"
            "Call ReplaceFiles(dir)\n"
            "Call LogMsg(dir, \"[replaced] \" & Now)\n"
            "launched = False\n"
            "For i = 1 To 3\n"
            "  shell.Run Chr(34) & dir & \"\\Judo_Club_Seddouk.exe\" & Chr(34), 1, False\n"
            "  WScript.Sleep 3000\n"
            "  If CheckRunning() Then\n"
            "    launched = True\n"
            "    Call LogMsg(dir, \"[relaunched] essai \" & i & \" \" & Now)\n"
            "    Exit For\n"
            "  End If\n"
            "Next\n"
            "If Not launched Then Call LogMsg(dir, \"[relaunch-failed] aucun processus detecte \" & Now)\n"
            "' Le journal update-log.txt est conserve volontairement pour diagnostic.\n"
            "fso.DeleteFile WScript.ScriptFullName\n"
            "\n"
            "Function CheckRunning()\n"
            "  Dim q\n"
            "  q = \"SELECT ProcessId FROM Win32_Process WHERE Name='Judo_Club_Seddouk.exe'\"\n"
            "  If GetObject(\"winmgmts:\\\\.\\root\\cimv2\").ExecQuery(q).Count > 0 Then\n"
            "    CheckRunning = True\n"
            "  Else\n"
            "    CheckRunning = False\n"
            "  End If\n"
            "End Function\n"
            "\n"
            "Sub ReplaceFiles(dir)\n"
            "  Dim attempt\n"
            "  For attempt = 1 To 20\n"
            "    On Error Resume Next\n"
            "    fso.DeleteFile dir & \"\\Judo_Club_Seddouk.exe\", True\n"
            "    fso.MoveFile dir & \"\\Judo_Club_Seddouk.new.exe\", dir & \"\\Judo_Club_Seddouk.exe\"\n"
            "    If Err.Number = 0 And fso.FileExists(dir & \"\\Judo_Club_Seddouk.exe\") Then Exit For\n"
            "    Err.Clear\n"
            "    On Error GoTo 0\n"
            "    WScript.Sleep 1000\n"
            "  Next\n"
            "  On Error GoTo 0\n"
            "End Sub\n"
            "\n"
            "Sub LogMsg(dir, msg)\n"
            "  Dim f\n"
            "  On Error Resume Next\n"
            "  Set f = fso.OpenTextFile(dir & \"\\update-log.txt\", 8, True)\n"
            "  f.WriteLine msg\n"
            "  f.Close\n"
            "  On Error GoTo 0\n"
            "End Sub\n"
        )
        try:
            with open(cmd_path, "w", encoding="utf-8") as f:
                f.write(script)
            try:
                with open(os.path.join(APP_DIR, "update-log.txt"), "a", encoding="utf-8") as f:
                    f.write("[server] apply lance %s (%d octets)\n" % (datetime.datetime.now().isoformat(timespec="seconds"), os.path.getsize(dest)))
            except OSError:
                pass
            CREATE_NO_WINDOW = 0x08000000
            # IMPORTANT : retirer les variables privées de PyInstaller (_PYI_*) de
            # l'environnement hérité. Sinon le nouvel EXE relancé par la VBS hérite de
            # _PYI_PARENT_PROCESS_LEVEL=1 (croit être le "child" d'une app onefile déjà
            # lancée) et échoue la validation de sécurité du bootloader avec
            # "Security validation failure: parent process has different executable!".
            env = dict(os.environ)
            for key in list(env):
                if key.startswith("_PYI_") or key in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP"):
                    env.pop(key, None)
            subprocess.Popen(
                ["wscript.exe", cmd_path],
                creationflags=CREATE_NO_WINDOW,
                env=env,
            )
            _schedule_close_after_apply()
            self._send_json({"ok": True})
        except Exception as e:
            self._send_json({"error": str(e)})


def open_browser():
    threading.Timer(1.0, lambda: webbrowser.open("http://%s:%d" % (HOST, PORT))).start()


def _schedule_close_after_apply():
    """Filet de sécurité : même si l'appel JS pywebview.close_app() échoue,
    la fenêtre se ferme ~2,5 s après le clic (la VBS force ensuite si besoin)."""
    api = Api._current
    if api is None:
        return

    def _close():
        try:
            api.close_app()
        except Exception:
            pass

    threading.Timer(2.5, _close).start()


class Api:
    """Pont JS <-> Python : permet d'ouvrir la fiche / le badge dans une
    nouvelle fenêtre du logiciel (au lieu de window.open d'un navigateur),
    et de fermer proprement l'application après une mise à jour."""

    current = None

    def __init__(self, base_url):
        self._base_url = base_url
        self._main_window = None
        self._child_windows = []
        Api._current = self

    def open_file(self, rel_url):
        import webview
        try:
            url = self._base_url + "/" + unquote(rel_url.lstrip("/"))
            w = webview.create_window(
                "Judo Club Seddouk", url, width=900, height=1200, min_size=(600, 700)
            )
            self._child_windows.append(w)
        except Exception as e:
            print("open_file error:", e)
        return True

    def close_app(self):
        """Ferme toutes les fenêtres : l'application quitte, puis le script
        de mise à jour remplace l'ancien EXE par le nouveau et le relance."""
        import webview
        try:
            for w in list(self._child_windows):
                try:
                    if w is not None:
                        w.destroy()
                except Exception:
                    pass
            if self._main_window is not None:
                self._main_window.destroy()
        except Exception as e:
            print("close_app error:", e)
        return True

    def save_export(self, data, filename):
        """Ouvre un 'Enregistrer sous' Windows et écrit la sauvegarde JSON
        à l'endroit choisi par l'utilisateur."""
        path = save_file_dialog(filename)
        if not path:
            return "canceled"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
        except OSError as e:
            return "error: %s" % e
        return "saved"


def _work_area():
    """Retourne (largeur, hauteur) de l'aire de travail de l'écran principal,
    en pixels logiques, via SystemParametersInfo(SPI_GETWORKAREA)."""
    import ctypes

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    r = RECT()
    if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
        return (r.right - r.left, r.bottom - r.top)
    return (1400, 850)


def run_gui(server):
    """Ouvre l'application dans une vraie fenêtre de logiciel (WebView2).
    Fermer la fenêtre arrête le serveur et quitte le programme."""
    import webview

    api = Api("http://%s:%d" % (HOST, PORT))

    # Grande fenêtre par défaut (~90 % de l'écran) avec les boutons classiques
    # réduire / agrandir / fermer. Pas le plein écran, pas de window.maximize()
    # (buggé avec ce pilote : récursion infinie -> repli navigateur).
    w, h = _work_area()
    window = webview.create_window(
        "Judo Club Seddouk — Gestion des Adhérents",
        "http://%s:%d/" % (HOST, PORT),
        width=int(w * 0.9),
        height=int(h * 0.9),
        min_size=(1024, 700),
        js_api=api,
    )
    api._main_window = window

    def stop_server():
        threading.Thread(target=server.shutdown, daemon=True).start()

    window.events.closed += stop_server

    webview.start(gui=None, debug=False)
    server.server_close()


def main():
    init_db()
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        print("Impossible de démarrer le serveur sur le port %d : %s" % (PORT, e))
        _msgbox(
            "Judo Club Seddouk",
            "Impossible de démarrer le serveur sur le port %d.\n\n"
            "Le port est peut-être déjà utilisé. Fermez l'autre instance et réessayez." % PORT,
        )
        sys.exit(1)

    print("=" * 52)
    print("  JUDO CLUB SEDDOUK — Gestion des Adhérents")
    print("  URL       : http://%s:%d" % (HOST, PORT))
    print("  Base      : %s" % DB_PATH)
    print("=" * 52)
    print("  Fermez la fenêtre pour arrêter le serveur.")

    serve_thread = threading.Thread(target=server.serve_forever, daemon=True)
    serve_thread.start()

    try:
        # Fenêtre native du logiciel (fermer la fenêtre = arrêter le serveur).
        run_gui(server)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Fenêtre native indisponible (%s) — ouverture dans le navigateur." % e)
        open_browser()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    finally:
        server.server_close()


if __name__ == "__main__":
    _fix_stdio()
    try:
        main()
    except Exception as e:
        _msgbox("Judo Club Seddouk — Erreur", "Erreur inattendue : %s" % e)
        raise