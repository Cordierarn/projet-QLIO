# ✅ Nettoyage terminé - Projet QLIO

## État actuel du projet

Le projet a été nettoyé et ne contient plus que les **fichiers essentiels** :

### 📁 Fichiers présents

```
Projet QLIO/
├── docker-compose.yml          # Configuration Docker
├── FestoMES-2025-03-27.sql    # Dump de la base de données
├── robotino_data.csv          # Données du Robotino
├── data/                      # Données persistantes MariaDB
├── .gitignore                 # Fichiers à ignorer
└── README.md                  # Documentation
```

### ❌ Fichiers supprimés

Tous les fichiers Python et l'application ont été supprimés :
- app.py, dashboard.py, database.py, config.py
- robotino_analyzer.py
- Tous les README et guides
- Scripts de démarrage (.bat, .ps1)
- Dossiers assets/ et __pycache__/
- requirements.txt

---

## 🚀 Ce qui fonctionne actuellement

### ✅ Docker & Base de données

Les conteneurs Docker sont **actifs** :
- **MariaDB** : localhost:3306
- **phpMyAdmin** : http://localhost:8080

### 📊 Accès à la base de données

**Via phpMyAdmin (http://localhost:8080)** :
- Utilisateur : `root`
- Mot de passe : `example_root_password`

**Via ligne de commande** :
```powershell
docker exec -it projetqlio-mariadb-1 mariadb -uroot -pexample_root_password MES4
```

---

## 📚 Données disponibles

### Base de données MES4
- **65 tables** de production
- Données complètes de la ligne Festo
- Ordres, étapes, ressources, erreurs, etc.

### Fichier CSV Robotino
- **1,692,593 octets** de données
- Trajectoire, vitesse, énergie du robot mobile

---

## 🔧 Commandes utiles

### Démarrer Docker
```powershell
cd "l:\BUT\SD\Promo 2023\acordier\SD_3\Projet QLIO"
docker-compose up -d
```

### Arrêter Docker
```powershell
docker-compose down
```

### Voir les logs
```powershell
docker-compose logs mariadb
docker-compose logs phpmyadmin
```

### Vérifier l'état
```powershell
docker ps
```

---

## 💡 Pour développer une application

Si vous voulez recréer une application dashboard, utilisez ces paramètres de connexion :

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'example_root_password',
    'database': 'MES4'
}
```

---

## 📝 Résumé

✅ **Projet nettoyé avec succès**
✅ **Docker fonctionne** (MariaDB + phpMyAdmin)
✅ **Base MES4 accessible**
✅ **Données CSV Robotino disponibles**

Le projet est maintenant dans son **état minimal** avec uniquement l'infrastructure de base de données.
