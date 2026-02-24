# 🏭 Dashboard MES 4.0 – Projet QLIO

> Dashboard Streamlit de pilotage industriel pour la plateforme **Festo MES 4.0** et le robot **Robotino**.  
> Données stockées dans **MariaDB** (Docker), visualisation via **Streamlit + Altair**.

---

## 📋 Table des matières

1. [Prérequis](#-prérequis)
2. [Installation pas à pas](#-installation-pas-à-pas)
3. [Lancement du projet](#-lancement-du-projet)
4. [Accès aux interfaces](#-accès-aux-interfaces)
5. [Configuration avancée](#-configuration-avancée)
6. [Structure du projet](#-structure-du-projet)
7. [KPIs couverts](#-kpis-couverts)
8. [Dépannage](#-dépannage)
9. [Idées d'évolution](#-idées-dévolution)

---

## 🔧 Prérequis

Avant de commencer, vérifiez que les outils suivants sont installés sur votre machine :

| Outil | Version minimum | Lien de téléchargement |
|-------|----------------|----------------------|
| **Git** | 2.30+ | https://git-scm.com/downloads |
| **Docker Desktop** | 4.0+ | https://www.docker.com/products/docker-desktop/ |
| **Python** | 3.10+ | https://www.python.org/downloads/ |
| **pip** | 21+ | Inclus avec Python |

### Vérifier l'installation

Ouvrez un terminal **PowerShell** et tapez :

```powershell
git --version
docker --version
docker compose version
python --version
pip --version
```

> ⚠️ **Docker Desktop doit être lancé** avant de continuer. Vérifiez que l'icône Docker est visible dans la barre des tâches et qu'il indique "Docker Desktop is running".

---

## 📦 Installation pas à pas

### 1. Cloner le dépôt

```powershell
git clone https://github.com/Cordierarn/projet-QLIO.git
cd projet-QLIO
```

### 2. Créer un environnement virtuel Python (recommandé)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> 💡 Si vous obtenez une erreur de politique d'exécution PowerShell, exécutez d'abord :
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### 3. Installer les dépendances Python

```powershell
pip install -r requirements.txt
```

Les packages installés :

| Package | Rôle |
|---------|------|
| `streamlit` | Framework web pour le dashboard |
| `pandas` | Manipulation des données |
| `sqlalchemy` | ORM / connexion à la BDD |
| `pymysql` | Driver MySQL/MariaDB pour Python |
| `altair` | Graphiques interactifs |

### 4. Démarrer les conteneurs Docker (MariaDB + phpMyAdmin)

```powershell
docker compose up -d
```

Cela démarre deux services :
- **MariaDB** sur le port `3306` – base de données
- **phpMyAdmin** sur le port `8080` – interface web pour la BDD

Vérifiez que les conteneurs tournent :

```powershell
docker ps
```

Vous devez voir deux conteneurs en état `Up` :
```
NAMES                      PORTS
projetqlio-mariadb-1       0.0.0.0:3306->3306/tcp
projetqlio-phpmyadmin-1    0.0.0.0:8080->80/tcp
```

### 5. Importer le dump SQL dans MariaDB

> ⚠️ **Étape indispensable** – La base de données est vide au premier démarrage. Il faut importer le fichier SQL fourni.

**Option A – Via la ligne de commande (recommandé) :**

```powershell
# Attendre ~10 secondes que MariaDB soit prêt, puis :
cmd /c "docker exec -i projetqlio-mariadb-1 mariadb -u root -pexample_root_password MES4 < FestoMES-2025-03-27.sql"
```

**Option B – Via phpMyAdmin (interface graphique) :**

1. Ouvrir http://localhost:8080 dans votre navigateur
2. Sélectionner la base `MES4` dans le panneau de gauche
3. Cliquer sur l'onglet **Importer**
4. Choisir le fichier `FestoMES-2025-03-27.sql`
5. Cliquer sur **Exécuter**

### 6. Vérifier l'import

```powershell
docker exec projetqlio-mariadb-1 mariadb -u root -pexample_root_password MES4 -e "SHOW TABLES;"
```

Vous devez voir une liste de tables dont : `tblfinorder`, `tblfinorderpos`, `tblfinstep`, `tblmachinereport`, `tblorder`, `tblstep`, etc.

---

## 🚀 Lancement du projet

```powershell
streamlit run app.py
```

Le dashboard s'ouvre automatiquement dans votre navigateur à l'adresse :  
👉 **http://localhost:8501**

> 💡 Pour arrêter l'application, appuyez sur `Ctrl+C` dans le terminal.

---

## 🌐 Accès aux interfaces

| Service | URL | Identifiants |
|---------|-----|-------------|
| **Dashboard Streamlit** | http://localhost:8501 | – |
| **phpMyAdmin** | http://localhost:8080 | `root` / `example_root_password` |
| **MariaDB** (direct) | `localhost:3306` | `root` / `example_root_password` |

---

## ⚙️ Configuration avancée

### Variables d'environnement

La connexion à la base peut être personnalisée via des variables d'environnement :

| Variable | Valeur par défaut | Description |
|----------|------------------|-------------|
| `DB_HOST` | `localhost` | Hôte de la base de données |
| `DB_PORT` | `3306` | Port de MariaDB |
| `DB_USER` | `root` | Utilisateur BDD |
| `DB_PASSWORD` | `example_root_password` | Mot de passe BDD |
| `DB_NAME` | `MES4` | Nom de la base |

Exemple pour changer l'hôte :

```powershell
$env:DB_HOST = "192.168.1.100"
streamlit run app.py
```

### Données Robotino

Le fichier `robotino_data.csv` doit être placé **à la racine du projet** (même dossier que `app.py`). Il est lu automatiquement par le dashboard pour afficher les métriques du Robotino (trajectoire, vitesse, consommation).

---

## 📁 Structure du projet

```
projet-QLIO/
├── app.py                          # Application Streamlit principale
├── docker-compose.yml              # Configuration Docker (MariaDB + phpMyAdmin)
├── FestoMES-2025-03-27.sql         # Dump de la base de données MES4
├── requirements.txt                # Dépendances Python
├── robotino_data.csv               # Données du robot Robotino
├── README.md                       # Ce fichier
├── STATUS.md                       # Suivi d'avancement
├── .gitignore                      # Fichiers exclus du versioning
└── data/                           # Volume Docker MariaDB (ignoré par Git)
```

---

## 📊 KPIs couverts

| KPI | Source | Description |
|-----|--------|-------------|
| **Pièces en cours** | `tblstep` | Nombre d'étapes actives (`Active=1`) |
| **Taux d'avancement** | `tblorder` + `tblfinorder` | Ordres en cours / (planifiés + terminés) |
| **Lead time (Δ prévu/réel)** | `tblfinorderpos` | Écart entre durée planifiée et réelle |
| **Ordres terminés / jour** | `tblfinorder` | Histogramme journalier |
| **TRS / OEE** | `tblmachinereport` + `tblfinstep` | Disponibilité × Performance × Qualité |
| **Taux d'occupation machine** | `tblmachinereport` | Ratio Busy / total par ressource |
| **Top erreurs** | `tblfinstep` + `tblmainterror` | Erreurs les plus fréquentes |
| **First Pass Yield** | `tblfinstep` | % d'ordres sans erreur au 1er passage |
| **Temps moyen d'arrêt** | `tblmachinereport` | Durée moyenne des séquences d'erreur |
| **Remplissage buffers** | `tblbufferpos` | Taux d'occupation des positions de buffer |
| **Énergie par étape** | `tblfinstep` | Consommation électrique réelle vs calculée |
| **Robotino** | `robotino_data.csv` | Distance, vitesse, puissance, trajectoire |

---

## 🔥 Dépannage

### « Connexion BDD impossible »

1. Vérifiez que Docker tourne : `docker ps`
2. Vérifiez que l'import SQL a été fait (voir [étape 5](#5-importer-le-dump-sql-dans-mariadb))
3. Testez la connexion manuellement :
   ```powershell
   docker exec projetqlio-mariadb-1 mariadb -u root -pexample_root_password MES4 -e "SELECT 1;"
   ```

### « Table 'xxx' doesn't exist »

L'import SQL n'a pas été effectué. Refaites l'[étape 5](#5-importer-le-dump-sql-dans-mariadb).

### « Port 3306 already in use »

Un autre service MySQL/MariaDB tourne déjà sur votre machine. Arrêtez-le ou changez le port dans `docker-compose.yml` :

```yaml
ports:
  - "3307:3306"   # Utiliser le port 3307 à la place
```

Puis mettez à jour la variable d'environnement :
```powershell
$env:DB_PORT = "3307"
```

### « Set-ExecutionPolicy » erreur PowerShell

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Docker Desktop ne démarre pas

- Windows : activez **WSL 2** et **Hyper-V** dans les fonctionnalités Windows
- Redémarrez votre PC après l'installation de Docker Desktop

### Le dashboard est lent au premier chargement

C'est normal. Les données sont mises en cache pendant 5 minutes (TTL=300s). Les rechargements suivants seront rapides.

---

## 💡 Idées d'évolution

- Relier les données Robotino aux ordres de fabrication via les timestamps
- Heatmap des vitesses/arrêts du Robotino et alertes batterie
- Export PDF des rapports
- Alerting automatique quand le TRS descend sous un seuil
- Tests de performance sous charge (caches, agrégations matérialisées)
- Ajout d'un système d'authentification utilisateur

---

## 👥 Auteurs

- **Arnaud Cordier** – Étudiant BUT QLIO

---

*Projet réalisé dans le cadre du BUT QLIO – IUT*
