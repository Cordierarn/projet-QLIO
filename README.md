# Dashboard MES 4.0 – Groupe n°7

> Dashboard de pilotage industriel pour la plateforme **Festo MES 4.0**.  
> Backend **Flask (Python)**, frontend **HTML/CSS** avec icônes Lucide et graphiques ApexCharts.  
> Données stockées dans **MariaDB** (Docker).

---

## Table des matières

1. [Prérequis](#prérequis)
2. [Installation pas à pas](#installation-pas-à-pas)
3. [Lancement du projet](#lancement-du-projet)
4. [Accès aux interfaces](#accès-aux-interfaces)
5. [Configuration avancée](#configuration-avancée)
6. [Structure du projet](#structure-du-projet)
7. [KPIs couverts](#kpis-couverts)
8. [Dépannage](#dépannage)

---

## Prérequis

| Outil | Version minimum | Lien |
|-------|----------------|------|
| **Git** | 2.30+ | https://git-scm.com/downloads |
| **Docker Desktop** | 4.0+ | https://www.docker.com/products/docker-desktop/ |
| **Python** | 3.10+ | https://www.python.org/downloads/ |

> Docker Desktop doit être **lancé et en cours d'exécution** avant de continuer.  
> Python doit être ajouté au PATH lors de l'installation (cocher *"Add Python to PATH"*).

---

## Installation pas à pas

### 1. Cloner le dépôt

```powershell
git clone https://github.com/Cordierarn/projet-QLIO.git
cd projet-QLIO
```

### 2. Créer et activer l'environnement virtuel Python

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> Si PowerShell bloque les scripts :
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> Le prompt doit afficher `(venv)` en début de ligne.

### 3. Installer les dépendances Python

```powershell
pip install -r requirements.txt
```

### 4. Démarrer les conteneurs Docker

```powershell
docker compose up -d
```

Vérifier que les deux conteneurs sont actifs :

```powershell
docker ps
```

Résultat attendu :

```
CONTAINER ID   IMAGE                   NAMES      PORTS
xxxxxxxxxxxx   mariadb:latest          db_qlio    0.0.0.0:3306->3306/tcp
xxxxxxxxxxxx   phpmyadmin/phpmyadmin   pma_qlio   0.0.0.0:8080->80/tcp
```

### 5. Importer la base de données

> Étape indispensable — la base est vide au premier démarrage.

```powershell
# Étape 1 : copier le fichier SQL dans le conteneur
docker cp FestoMES-2026-03-31-2.sql db_qlio:/tmp/mes4.sql

# Étape 2 : importer (--binary-mode requis pour compatibilité HeidiSQL)
docker exec db_qlio bash -c "mariadb -u root -pexample_root_password --binary-mode --force < /tmp/mes4.sql"
```

### 6. Créer l'utilisateur applicatif

```powershell
docker exec db_qlio mariadb -u root -pexample_root_password -e "CREATE USER IF NOT EXISTS 'qlio_user'@'%' IDENTIFIED BY 'Qlio_MES4@2026'; GRANT SELECT ON mes4.* TO 'qlio_user'@'%'; FLUSH PRIVILEGES;"
```

> `qlio_user` dispose uniquement des droits `SELECT` — cela limite la surface d'attaque.

### 7. Vérifier l'import

```powershell
docker exec db_qlio mariadb -u root -pexample_root_password mes4 -e "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema='mes4' ORDER BY table_rows DESC LIMIT 10;"
```

Tables critiques attendues : `tblmachinereport` (~13 000+ lignes), `tblfinstep` (~1 600+), `tblfinorder` (~200+).

---

## Lancement du projet

Avec le venv activé et les conteneurs Docker en cours d'exécution :

```powershell
python app.py
```

Sortie attendue :

```
[T'Elefan MES 4.0] http://localhost:5000
 * Serving Flask app 'app'
 * Running on http://0.0.0.0:5000
```

Le dashboard est accessible à : **http://localhost:5000**

Pour arrêter : `Ctrl+C` dans le terminal.

---

## Accès aux interfaces

| Service | URL | Utilisateur | Mot de passe |
|---------|-----|-------------|-------------|
| **Dashboard – Administrateur** | http://localhost:5000 | `admin@telefan.fr` | `Admin@MES4_2026!` |
| **Dashboard – Opérateur** | http://localhost:5000 | `operateur@telefan.fr` | `Oper@Prod_2026` |
| **phpMyAdmin** | http://localhost:8080 | `root` | `example_root_password` |
| **MariaDB (app)** | `localhost:3306` | `qlio_user` | `Qlio_MES4@2026` |
| **MariaDB (admin)** | `localhost:3306` | `root` | `example_root_password` |

---

## Configuration avancée

### Variables d'environnement

| Variable | Valeur par défaut | Description |
|----------|------------------|-------------|
| `DB_HOST` | `localhost` | Hôte MariaDB |
| `DB_PORT` | `3306` | Port MariaDB |
| `DB_USER` | `qlio_user` | Utilisateur BDD |
| `DB_PASSWORD` | `Qlio_MES4@2026` | Mot de passe BDD |
| `DB_NAME` | `mes4` | Nom de la base |
| `ADMIN_EMAIL` | `admin@telefan.fr` | Email admin dashboard |
| `ADMIN_PASSWORD` | `Admin@MES4_2026!` | Mot de passe admin |
| `OPER_EMAIL` | `operateur@telefan.fr` | Email opérateur |
| `OPER_PASSWORD` | `Oper@Prod_2026` | Mot de passe opérateur |
| `SECRET_KEY` | `telefan-mes-4-secret-2026` | Clé de session Flask |
| `PORT` | `5000` | Port Flask |

Exemple :

```powershell
$env:DB_PORT = "3307"
python app.py
```

---

## Structure du projet

```
projet-QLIO/
├── app.py                      # Backend Flask (routes, auth, KPIs)
├── db.py                       # Requêtes SQL et fonctions KPI
├── requirements.txt            # Dépendances Python (versions exactes)
├── docker-compose.yml          # MariaDB (db_qlio) + phpMyAdmin (pma_qlio)
├── FestoMES-2026-03-31-2.sql   # Dump complet Festo MES 4.0
├── data_all.csv                # Données capteurs Robotino (puissance, pression, débit)
├── dataEnergy.csv              # Série temporelle énergie (phases L1/L2/L3)
├── templates/
│   ├── base.html               # Layout : sidebar, header, CDN JS
│   ├── login.html              # Page de connexion
│   ├── 404.html                # Page d'erreur 404
│   ├── dashboard.html          # Accueil – Vue générale
│   ├── production.html         # KPI 1 à 4 – Suivi des OF
│   ├── qualite.html            # KPI 5 à 9 – TRS, erreurs
│   ├── machines.html           # KPI 10 – Temps d'arrêt
│   ├── maintenance.html        # KPI 11-12 – Buffers, énergie
│   └── geographie.html         # Site – Carte Leaflet + infos IUT
└── static/
    ├── css/
    │   └── style.css           # Thème sombre T'Elefan
    └── img/
        └── logo_telefan.png    # Logo T'Elefan
```

---

## KPIs couverts

### Production (KPI 1–4)

| KPI | Source | Description |
|-----|--------|-------------|
| **KPI 1** – Produits en cours | `tblstep` | Produits actifs (distinct ONo/OPos, `Active=1`) |
| **KPI 2** – Lead Time | `tblfinorderpos` | Écart durée planifiée vs réelle |
| **KPI 3** – Avancement OF | `tblorderpos` | Produits terminés / total (top 3 FIFO) |
| **KPI 4** – OF terminés/jour | `tblfinorder` | Histogramme journalier |

### Qualité (KPI 5–9)

| KPI | Source | Description |
|-----|--------|-------------|
| **KPI 5** – TRS / OEE | `tblmachinereport` + `tblfinstep` | Disponibilité × Performance × Qualité |
| **KPI 6** – Occupation machines | `tblmachinereport` | Taux Busy par ressource |
| **KPI 7** – Erreurs totales | `tblfinstep` | Nombre total d'erreurs détectées |
| **KPI 8** – Pareto erreurs | `tblfinstep` + `tblmainterror` | Erreurs les plus fréquentes par étape |
| **KPI 9** – First Pass Yield | `tblfinstep` | % d'ordres sans erreur au 1er passage |

### Machines (KPI 10)

| KPI | Source | Description |
|-----|--------|-------------|
| **KPI 10** – Temps d'arrêt | `tblmachinereport` | MTBF, MTTR, pannes par ressource |

### Maintenance (KPI 11–12)

| KPI | Source | Description |
|-----|--------|-------------|
| **KPI 11** – Buffers | `tblbufferpos` | Taux de remplissage par buffer |
| **KPI 12** – Énergie | `tblfinstep` + `data_all.csv` + `dataEnergy.csv` | Consommation réelle vs calculée + courbes capteurs |

---

## Dépannage

### Erreur de connexion BDD

```
pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
```

Docker n'est pas démarré ou les conteneurs ne tournent pas :

```powershell
docker ps
docker compose up -d
```

### Page blanche / KPIs à zéro

L'import SQL n'a pas été effectué. Reprendre l'étape 5.

### `Activate.ps1 cannot be loaded`

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Port 3306 déjà utilisé

Modifier `docker-compose.yml` → `"3307:3306"`, puis :

```powershell
$env:DB_PORT = "3307"
python app.py
```

### Port 5000 déjà utilisé

```powershell
$env:PORT = "5001"
python app.py
```

---

## Auteurs

**Arnaud Cordier** · **Corentin Seu** · **Alem Nadji** — Groupe n°7  
*BUT Science des Données – IUT Lumière Lyon 2*
