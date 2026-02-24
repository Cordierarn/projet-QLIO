# Dashboard MES 4.0 – Groupe n°7

> Dashboard de pilotage industriel pour la plateforme **Festo MES 4.0**.
> Backend **Flask (Python)**, frontend **HTML/CSS** avec icônes SVG Lucide et graphiques ApexCharts.
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

> Docker Desktop doit être **lancé** avant de continuer.

---

## Installation pas à pas

### 1. Cloner le dépôt

```powershell
git clone https://github.com/Cordierarn/projet-QLIO.git
cd projet-QLIO
```

### 2. Créer un environnement virtuel Python

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Installer les dépendances Python

```powershell
pip install -r requirements.txt
```

| Package | Rôle |
|---------|------|
| `flask` | Framework web backend |
| `pandas` | Manipulation des données |
| `sqlalchemy` | Connexion à la base de données |
| `pymysql` | Driver MySQL/MariaDB |

### 4. Démarrer les conteneurs Docker (MariaDB + phpMyAdmin)

```powershell
docker compose up -d
```

Vérifiez que les conteneurs tournent :

```powershell
docker ps
```

```
NAMES                      PORTS
projetqlio-mariadb-1       0.0.0.0:3306->3306/tcp
projetqlio-phpmyadmin-1    0.0.0.0:8080->80/tcp
```

### 5. Importer le dump SQL dans MariaDB

> Étape indispensable — la base est vide au premier démarrage.


**phpMyAdmin :**

1. Ouvrir http://localhost:8080
2. Sélectionner la base `MES4`
3. Onglet **Importer** → choisir `FestoMES-2025-11-25-v2.sql` → **Exécuter**

### 6. Vérifier l'import

```powershell
docker exec projetqlio-mariadb-1 mariadb -u root -pexample_root_password MES4 -e "SHOW TABLES;"
```

Vous devez voir : `tblfinorder`, `tblfinorderpos`, `tblfinstep`, `tblmachinereport`, etc.

---

## Lancement du projet

```powershell
python app.py
```

Le dashboard est accessible à :
**http://localhost:5000**

**Identifiants par défaut :**

| Champ | Valeur |
|-------|--------|
| Email | `admin@telefan.fr` |
| Mot de passe | `telefan2026` |

> Pour arrêter l'application : `Ctrl+C` dans le terminal.

---

## Accès aux interfaces

| Service | URL | Identifiants |
|---------|-----|-------------|
| **Dashboard MES 4.0** | http://localhost:5000 | `admin@telefan.fr` / `telefan2026` |
| **phpMyAdmin** | http://localhost:8080 | `root` / `example_root_password` |
| **MariaDB** (direct) | `localhost:3306` | `root` / `example_root_password` |

---

## Configuration avancée

### Variables d'environnement

| Variable | Valeur par défaut | Description |
|----------|------------------|-------------|
| `DB_HOST` | `localhost` | Hôte de la base de données |
| `DB_PORT` | `3306` | Port de MariaDB |
| `DB_USER` | `root` | Utilisateur BDD |
| `DB_PASSWORD` | `example_root_password` | Mot de passe BDD |
| `DB_NAME` | `MES4` | Nom de la base |
| `ADMIN_EMAIL` | `admin@telefan.fr` | Email de connexion au dashboard |
| `ADMIN_PASSWORD` | `telefan2026` | Mot de passe de connexion |
| `SECRET_KEY` | `telefan-mes-4-secret-2026` | Clé de session Flask |
| `PORT` | `5000` | Port d'écoute Flask |

Exemple :

```powershell
$env:DB_HOST = "192.168.1.100"
$env:ADMIN_PASSWORD = "mon_mot_de_passe"
python app.py
```

---

## Structure du projet

```
projet-QLIO/
├── app.py                      # Backend Flask (routes, auth, données)
├── db.py                       # Requêtes SQL et fonctions KPI
├── requirements.txt            # Dépendances Python
├── docker-compose.yml          # MariaDB + phpMyAdmin
├── FestoMES-2025-11-25-v2.sql  # Dump base de données (version courante)
├── templates/
│   ├── base.html               # Layout : sidebar, header, CDN JS
│   ├── login.html              # Page de connexion
│   ├── dashboard.html          # Accueil – Vue générale
│   ├── production.html         # KPI 1 à 4 – Suivi des OF
│   ├── qualite.html            # KPI 5 à 9 – TRS, erreurs
│   ├── machines.html           # KPI 10 – Temps d'arrêt
│   └── maintenance.html        # KPI 11-12 – Buffers, énergie
└── static/
    └── css/
        └── style.css           # Thème sombre T'Elefan
```

---

## KPIs couverts

### Production (KPI 1–4)

| KPI | Source | Description |
|-----|--------|-------------|
| **KPI 1** – OF en cours | `tblstep` | Nombre d'étapes actives (`Active=1`) |
| **KPI 2** – Lead Time | `tblfinorderpos` | Écart entre durée planifiée et réelle |
| **KPI 3** – Taux d'avancement | `tblorder` + `tblfinorder` | Progression des OF actifs |
| **KPI 4** – OF terminés | `tblfinorder` | Histogramme des ordres terminés/jour |

### Qualité (KPI 5–9)

| KPI | Source | Description |
|-----|--------|-------------|
| **KPI 5** – TRS / OEE | `tblmachinereport` + `tblfinstep` | Disponibilité × Performance × Qualité |
| **KPI 6** – Occupation | `tblmachinereport` | Taux Busy par ressource |
| **KPI 7** – Erreurs | `tblfinstep` | Total d'erreurs détectées |
| **KPI 8** – Pareto erreurs | `tblfinstep` + `tblmainterror` | Erreurs les plus fréquentes |
| **KPI 9** – First Pass Yield | `tblfinstep` | % d'ordres sans erreur au 1er passage |

### Machines (KPI 10)

| KPI | Source | Description |
|-----|--------|-------------|
| **KPI 10** – Temps d'arrêt | `tblmachinereport` | MTBF, MTTR, arrêts par ressource |

### Maintenance (KPI 11–12)

| KPI | Source | Description |
|-----|--------|-------------|
| **KPI 11** – Buffers | `tblbufferpos` | Taux de remplissage par buffer |
| **KPI 12** – Énergie | `tblfinstep` | Consommation électrique réelle vs calculée |

---

## Dépannage

### Connexion BDD impossible

1. Vérifier Docker : `docker ps`
2. Vérifier l'import SQL (voir étape 5)
3. Tester manuellement :
   ```powershell
   docker exec projetqlio-mariadb-1 mariadb -u root -pexample_root_password MES4 -e "SELECT 1;"
   ```

### Table 'xxx' doesn't exist

L'import SQL n'a pas été effectué. Refaire l'étape 5.

### Port 3306 déjà utilisé

Modifier `docker-compose.yml` :
```yaml
ports:
  - "3307:3306"
```
Puis : `$env:DB_PORT = "3307"`

### Port 5000 déjà utilisé

```powershell
$env:PORT = "5001"
python app.py
```

---

## Auteurs

**Arnaud Cordier** · **Corentin Seu** · **Alem Nadji** — Groupe n°7

*Projet réalisé dans le cadre du BUT SD – IUT*
