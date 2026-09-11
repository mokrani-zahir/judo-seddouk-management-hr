# JUDO CLUB SEDDOUK — Gestion des Adhérents

Application Windows de gestion des adhérents (Judo Club Seddouk), distribuée sous
forme d'un EXE portable autonome, avec mise à jour automatique depuis GitHub.

---

## ENVIRONNEMENT & OUTILS (à utiliser systématiquement)

- Windows 11, shell : **PowerShell 5.1** (PAS de `&&` ; utiliser `;` ou `if ($?) { ... }`).
- Python : **3.10.9** ; PyInstaller 6.22.2 ; pywebview 6.2.1 ; WebView2 (driver `edgechromium`).
- Pillow installé en dev (conversion logo → icône). `pip install pillow` sinon.
- **Git :** jamais `git add -A`. Toujours ajouter fichier par fichier.
  Remote = `mokrani-zahir/judo-seddouk-management-hr`, branche **`master`**.
- **GitHub via `curl.exe` UNIQUEMENT** (le poste passe par un proxy ; `Invoke-RestMethod` en PowerShell échoue). `curl.exe -s` pour lire raw/API/Télécharger.
- Dossiers de builds sauvegardés : `C:\Users\PC\AppData\Local\Temp\opencode\build_11NN\dist\`. Barre des tâches / fichiers temporaires : `C:\Users\PC\AppData\Local\Temp\opencode`.
- Commandes de vérification locales : `curl.exe --noproxy '*' -s http://127.0.0.1:8000/...` (l'app sert le port 8000).

---

## ARCHITECTURE

- **`serveur.py`** : tout le backend — serveur HTTP (`ThreadingHTTPServer`, `Handler`), base SQLite (`judo.db`), classe `Api` exposée à pywebview, mécanisme de mise à jour. `APP_VERSION` y est défini (ligne ~30).
- **`index.html`** : SPA (header sticky : Export/Import/Mise à jour + Badge/Formulaire vierges ; toolbar : recherche, filtre, Nouvel adhérent). Utilise `apiFetch` (retries réseau), `closeAppNow()`, `applyUpdate()`, `createDirectDoc()`.
- **3 documents HTML** copiés dans l'EXE via `--add-data` : `Fiche de renseignement Judo Club Seddouk.html`, `Badge_B3_Judo_Club_Seddouk_115x94mm.html`, `Badge_B3_Judo_Club_Seddouk_115x94mm-recto.html`.
- **`judo.db`** : SQLite. Table `adherents` (colonne `numero`, ...).
- **`app.ico`** : icône EXE (créée depuis `logo.png`, multi-tailles 16→256).
- **`api-ms-win-core-path-l1-1-0.dll`** : DLL "hack" (Wine, repo `nalexandru/api-ms-win-core-path-HACK`, release 0.3.1 x64) requise pour **Windows 7** (Python 3.9+ n'existe pas sur Win7). Embarquée dans l'EXE via `--add-binary` → l'EXE unique marche sur Win10 **et** Win7. Sur Win7, il faut aussi le **runtime WebView2** installé (sinon repli navigateur).
- **`version_info.txt`** : métadonnées/version Windows, à synchroniser avec `APP_VERSION` à chaque bump.
- **`version.json`** : publié sur GitHub, déclencheur de la mise à jour (`{ "version", "notes", "exe_url" }`).

---

## MODÈLE DE STOCKAGE (définitif — dixm d'utilisateur)

La base **`judo.db` est TOUJOURS dans `%APPDATA%\JudoClubSeddouk\judo.db`**, quel que soit
l'emplacement de l'EXE (qui peut être n'importe où sur le PC).
Logique `data_path()` (serveur.py) :
1. Créer `%APPDATA%\JudoClubSeddouk` ; cible = `judo.db` dedans.
2. Si la cible n'existe pas mais qu'une base existe **à côté de l'EXE** (ancienne version) → copie vers `%APPDATA%` et l'utilise (récupération automatique).
3. Si aucune base nulle part → base vide créée (schema via `init_db()`).

- `APP_DIR = dirname(DB_PATH)` → pointe toujours sur le dossier `%APPDATA%`.
- `EXE_DIR = dirname(sys.executable)` (frozen) → dossier réel de l'EXE, **utilisé pour la mise à jour**.

---

## MISE À JOUR AUTOMATIQUE (architecture actuelle — PAS de script)

Le mécanisme ne doit JAMAIS utiliser `wscript`/VBS/`update-install.vbs` (causes de
faux positifs antivirus + historiquement source de bugs).

### Téléchargement — `download_update()` / `_api_update_download`
- Écrit **`Judo_Club_Seddouk.new.exe` dans `EXE_DIR`** (à côté de l'EXE réel). ⚠️ Ne jamais utiliser `APP_DIR` ici.
- Vérifie `_dir_writable(EXE_DIR)` AVANT : si dossier protégé → message clair
  « déplacez l'application dans C:\JudoClubSeddouk » (et message au démarrage dans `run_gui()`).

### Applique — `_api_update_apply()` (_applying + `_apply_lock` anti-double)
- Garde-fou : `Handler._applying` + `threading.Lock` → un seul apply à la fois
  (un double apply a déjà SUPPRIMÉ l'EXE : second VBS qui taskkill + delete).
- Nettoie les variables `_PYI_*` / `PYTHONHOME` etc. de l'environnement hérité
  (sinon « Security validation failure » du bootloader : il croit être l'enfant
  d'une app onefile déjà lancée).
- Lance `subprocess.Popen([dest])` (le `.new.exe`) avec `env["JUDO_UPDATE"]="1"`, `CREATE_NO_WINDOW`, `cwd=EXE_DIR`.
- `_schedule_close_after_apply()` → ferme la fenêtre ~2,5 s plus tard (filet de sécurité).

### Mode mise à jour — `run_update_mode()` (exécuté par le NOUVEL EXE, `JUDO_UPDATE=1`)
- Dans `main()` : si frozen ET `JUDO_UPDATE=="1"` → `run_update_mode(); return` (avant serveur/GUI).
- Attend ~4 s (fermeture propre de l'ancienne), vérifie l'ancienne version via
  `tasklist /fi "IMAGENAME eq Judo_Club_Seddouk.exe"` (le `.new` n'est pas compté),
  sinon `taskkill /f /im Judo_Club_Seddouk.exe` (SANS `/t`).
- `shutil.copy2(new_exe, app_exe)` avec retries (20×1s) → remplace l'EXE.
- Relance `app_exe` avec env nettoyé (sans `JUDO_UPDATE`).
- Journal : `update-log.txt` à côté de l'EXE.
- Nettoyage : au démarrage normal, `main()` supprime le `.new.exe` résiduel
  (l'installeur ne peut pas se supprimer lui-même, Windows verrouille l'EXE en cours d'exécution).

---

## HISTORIQUE DES BUGS CORRIGÉS (ne pas réintroduire)

| Version | Bug / cause racine | Correctif |
|---|---|---|
| 1.1.4/5 | « Security validation failure » | retirer `_PYI_*` de l'env du Popen |
| 1.1.8 | `taskkill /f /t` tuait wscript (l'installeur lui-même, descendant du process) | `taskkill /f /im` sans `/t` |
| 1.1.10/11 | `window.maximize()` crashait PyInstaller → repli navigateur | contourné |
| 1.1.14 | récursion infinie pywebview : `webview.util.get_functions` introspectait `Api.main_window` (Window) → `.native.AccessibilityObject` → récursion → lecteur UI bloqué | renommer TOUS les attributs exposés avec préfixe `_` : `_main_window`, `_child_windows`, `_base_url`, `_current` |
| 1.1.16 | rétabli `window.maximize()` (sûr après 1.1.14) → fenêtre maximisée □ à l'ouverture (`window.events.loaded += lambda: window.maximize()`) |
| 1.1.17 | « unable to open database file » sur autre PC | repli base vers `%APPDATA%` |
| 1.1.18-20 | **BUG MÉMOIRE CRITIQUE** : la base basculait `APP_DIR` ; l'update écrivait `.new.exe` dans `%APPDATA%` (où il n'y a pas d'EXE) → VBS erreur 80070002 « fichier introuvable » | séparer `EXE_DIR` (dossier EXE réel) pour TOUT le mécanisme d'update ; refus clair si dossier non inscriptible ; migration base |
| 1.1.20 | double-apply (2 VBS parallèles) → suppression de l'EXE | verrou `_applying` + `threading.Lock` |
| 1.1.21 | faux positifs antivirus (pattern VBS + téléchargement + auto-remplacement) | suppression totale de wscript/VBS → le `.new.exe` se remplace lui-même (voir architecture) ; + icône `--icon` et métadonnées `--version-file` |
| 1.1.22 | base pas toujours dans `%APPDATA%` (demande utilisateur) | `data_path()` : TOUJOURS `%APPDATA%\JudoClubSeddouk`, récupération auto de l'ancienne base à côté de l'EXE |
| 1.1.23 | icône du club | `app.ico` généré depuis `logo.png` (Pillow), recomplié, publé |
| 1.1.24 | exe ne démarre pas sur Windows 7 (`api-ms-win-core-path-l1-1-0.dll` manquante : Python 3.9+ = Win8+) | embarquement de la DLL hack (Wine) via `--add-binary` dans l'EXE unique ; sur Win7, installer aussi le runtime WebView2 |

---

## PROCÉDURE DE BUILD + PUBLICATION (obligatoire, dans l'ordre)

⚠️ **ERREUR COMMISE 2 FOIS : publier sans copier le nouvel EXE dans `dist\`.**
Après `--distpath"$stage\dist"`, il faut TOUJOURS : `Copy-Item "$stage\dist\Judo_Club_Seddouk.exe" "$p\dist\Judo_Club_Seddouk.exe" -Force` **puis** `git add` sur l'EXE de `dist`. Sinon GitHub reçoit l'ancien EXE alors que `version.json` annonce la nouvelle version (dercopage CDN + users bloqués).

1. **Bump la version partout** : `APP_VERSION` dans `serveur.py`, `version.json`, `version_info.txt`
   (filevers/prodvers + FileVersion/ProductVersion). `python -m py_compile serveur.py` pour valider.
2. **Tuer l'app en cours** : `Get-Process Judo_Club_Seddouk -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 2`.
3. **Build PyInstaller** (commande exacte) :
   ```
   $p="C:\Users\PC\Documents\Project\judo_seddouk"; $stage="C:\Users\PC\AppData\Local\Temp\opencode\build_11NN"
   Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
   python -m PyInstaller --onefile --noconsole --name "Judo_Club_Seddouk" --icon "$p\app.ico" --version-file "$p\version_info.txt" --add-data "$p\index.html;." --add-data "$p\Fiche de renseignement Judo Club Seddouk.html;." --add-data "$p\Badge_B3_Judo_Club_Seddouk_115x94mm.html;." --add-data "$p\Badge_B3_Judo_Club_Seddouk_115x94mm-recto.html;." --add-binary "$p\api-ms-win-core-path-l1-1-0.dll;." --hidden-import webview --hidden-import webview.platforms.winforms --hidden-import webview.platforms.edgechromium --hidden-import clr_loader --hidden-import pythonnet --distpath "$stage\dist" --workpath "$stage\build" --specpath "$stage" "$p\serveur.py"
   ```
4. **Copier l'EXE dans dist** : `Copy-Item "$stage\dist\Judo_Club_Seddouk.exe" "$p\dist\Judo_Club_Seddouk.exe" -Force` ;
   retirer les résidus `update-install.vbs`, `Judo_Club_Seddouk.new.exe`, `update-log.txt` de `dist`.
5. **Vérifier la bonne version** : `(Get-Item "$p\dist\Judo_Club_Seddouk.exe").VersionInfo.ProductVersion` doit = nouvelle version. Noter le hash : `(Get-FileHash ...).Hash`.
6. **Git** : `git add` de `serveur.py`, `version.json`, `version_info.txt`, `app.ico` (si changée), `dist\Judo_Club_Seddouk.exe` ; `git commit -m "vX.Y.Z - ..."` ; `git push` (branche master). Vérifier `git log --oneline -3`.
7. **Attendre la cohérence du CDN raw** (cache GitHub jusqu'à ~30 min) : boucle de polling
   jusqu'à `version.json`=`X.Y.Z` ET hash(raw exe) == hash local. Vérifier hash via :
   `curl.exe -s -o "$env:TEMP\raw_check.exe" https://raw.githubusercontent.com/mokrani-zahir/judo-seddouk-management-hr/master/dist/Judo_Club_Seddouk.exe` puis comparer SHA256.
   Vérifier par API qui n'est PAS cachée : `curl.exe -s https://api.github.com/repos/mokrani-zahir/judo-seddouk-management-hr/contents/version.json -H "Accept: application/vnd.github.raw+json"`.
8. **Test E2E local** (à chaque build) : remettre dans `dist\` un EXE de l'ancienne version
   (ex. `C:\Users\PC\AppData\Local\Temp\opencode\build_11NN`.exe précédent), supprimer
   `.new.exe`/`update-log.txt`, lancer (`Start-Process ... -WorkingDirectory "$p\dist"`),
   attendre `/api/version`, puis `download` (POST), puis `apply` (POST), vérifier la relance
   à la nouvelle version et le `update-log.txt` (`[replaced] ok`, pas de double `[start]`).
   ⚠️ Ne PAS faire download+apply deux fois d'affilée dans le même test (double-apply).

---

## PIÈGES & NOTATIONS IMPORTANTES

- `proxy` sur ce poste : GitHub & téléchargements → `curl.exe` (jamais Invoke-RestMethod). Le serveur HTTP local de l'app suit `urllib` sans proxy configuré : OK.
- **CDN stale** : `version.json` peut apparaître "à jour" AVANT que les octets de l'EXE soient propagés. Toujours vérifier le hash des octets du raw en plus du JSON.
- `window.maximize()` est rétabli et fixe (fenêtre □ maximisée à l'ouverture). Ne pas retirer les préfixes `_` des attributs de `Api`.
- `taskkill` : JAMAIS `/t` (tuerait nos propres processus enfants).
- Ne pas créer de commentaires inutiles dans le code ; respecter le style existant (Python docstrings en français, signatures simples).
- **Avenir**: pour diminuer encore les faux positifs antivirus, seule la signature de code (certificat) résout vraiment ; les exclusions dossiers sont la parade immédiate.

---

## ÉTAT ACTUEL
- **Dernière version : 1.1.24** — publiée et vérifiée (json + EXE cohérents sur GitHub). Compatibilité **Windows 7** (api-ms-win-core-path-l1-1-0.dll embarquée).
- L'app tourne en 1.1.24 sur ce PC (port 8000).
- **Win7 — installateur automatique** : `win7/install_Win7.bat` (**double-clic, aucune manipulation** : il se relance lui-même en administrateur via `powershell Start-Process -Verb RunAs` — l'utilisateur n'a qu'à cliquer "Oui" sur l'écran UAC). Il installe tout seul, par ordre :
  1. activation TLS 1.2 (registre Schannel, requis pour télécharger sur un Win7 non-à-jour) ;
  2. `Windows6.1-KB2533623-x64.msu` (dans `win7/`, SHA1 `8A59EA3C7378895791E6CDCA38CC2AD9E83BEBFF` ; sinon miroir `beny1226/Windows-7-KB2533623`) — corrige l'erreur `_socket`/KERNEL32 ;
  3. .NET Framework 4.8 (`linkid=2088631`) — requis pour que pywebview active WebView2 (winforms `_is_chromium` exige la Release >= 394802, i.e. .NET 4.6.2+) ;
  4. `vc_redist.x64.exe` (`aka.ms/vs/17/release`) ;
  5. WebView2 **109.0.1518.78** Fixed Version (cab `westinyang/WebView2RuntimeArchive`, dernière version compatible Win7 : 110+ échoue avec `PackageIdFromFullName…KERNEL32.dll`) → extrait vers `%ProgramFiles%\WebView2`, détection de `msedgewebview2.exe`, écriture `pv` dans `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` et `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` (machine + utilisateur) ;
  6. télécharge l'EXE 1.1.24 du repo sur `%PUBLIC%\Desktop`, affiche le résumé puis **redémarre seul** (15 s, annulable `shutdown /a`).
- Le bat tolère un dossier clé USB : si les fichiers (msu/cab/exe/installateurs) sont déjà à côté, ils sont réutilisés (téléchargement seulement si absent). Les téléchargements utilisent `bitsadmin` puis `certutil` en secours.
- **Piège syntaxe .bat** : le modificateur de taille de variable `for` DOIT matcher la casse (`%%~zs` avec `%%s`, PAS `%%~zS`) sinon cmd l'imprime littéralement.
- **Autre PC** : possède encore la 1.1.17 (dossier protégé) → NE PEUT pas s'auto-mettre à jour. Installer manuellement : télécharger `https://raw.githubusercontent.com/mokrani-zahir/judo-seddouk-management-hr/master/dist/Judo_Club_Seddouk.exe`, le placer n'importe où (ex. `C:\JudoClubSeddouk`), lancer ; la base `%APPDATA%` existante sera utilisée automatiquement.

## PROCHAINES ÉTAPES SUGGÉRÉES
- **Win7** : faire tourner `win7/install_Win7.bat` (clic droit → exécuter en tant qu'administrateur) sur le PC Win7 ; après redémarrage, l'exe est sur le Bureau. Vérifier que l'app 1.1.24 démarre bien (la base `%APPDATA%` existante sera utilisée automatiquement).
- Vérifier avec l'utilisateur le rendu de la nouvelle icône (il restait sur le cache Windows).
- Eventuellement recadrer `logo.png` (120×122) si le rendu 32×32 n'est pas net.
- Optionnel : version "installer signé / exclusions antivirus" pour l'autre PC.