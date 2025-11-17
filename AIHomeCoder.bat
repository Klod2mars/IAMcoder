# =====================================================
# 🧠 AIHomeCoder V1 — Lancement PowerShell direct
# =====================================================

# Aller dans le dossier du projet
Set-Location "C:\Users\roman\Documents\apppklod\aihomecoder"

# Activer l'environnement virtuel
& ".\venv\Scripts\Activate.ps1"

# Changer le titre de la fenêtre
$Host.UI.RawUI.WindowTitle = "🧠 AIHomeCoder V1 — Atelier Local"

# Message d'accueil
Write-Host ""
Write-Host "====================================================="
Write-Host "  🚀  Lancement de AIHomeCoder V1"
Write-Host "  🧠  Environnement Python activé"
Write-Host "====================================================="
Write-Host ""

# Lancer le moteur
python main.py version

# Laisser la console active
Write-Host ""
Write-Host "🪄 AIHomeCoder est prêt. Vous pouvez exécuter :"
Write-Host "   python main.py run example_mission.yalm --verbose"
Write-Host ""
