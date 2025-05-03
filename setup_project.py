import os
import shutil

# Créer les répertoires nécessaires
os.makedirs('templates', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/uploads', exist_ok=True)

# Liste des fichiers HTML à déplacer vers templates
html_files = ['login.html', 'index.html', 'result.html', 'gallery.html']

# Déplacer les fichiers HTML vers le dossier templates
for file in html_files:
    if os.path.exists(file):
        shutil.move(file, os.path.join('templates', file))
        print(f"Déplacé {file} vers templates/")

# Déplacer style.css vers static/css
if os.path.exists('style.css'):
    shutil.move('style.css', os.path.join('static', 'css', 'style.css'))
    print("Déplacé style.css vers static/css/")

print("Structure du projet configurée avec succès!")
