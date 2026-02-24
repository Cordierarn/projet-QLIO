## Dashboard MES 4.0 – Sprint 1

Une première version Streamlit pour suivre les indicateurs du cahier des charges QLIO à partir de la base MariaDB et du CSV Robotino.

### Prérequis
- Docker pour démarrer MariaDB/phpMyAdmin (`docker-compose up -d`).
- Python 3.10+ et `pip`.

### Installation rapide
```powershell
cd "l:\BUT\SD\Promo 2023\acordier\SD_3\Projet QLIO"
pip install -r requirements.txt
```

### Lancement
```powershell
streamlit run app.py
```
Par défaut la connexion utilise `root/example_root_password@localhost:3306/MES4`. Vous pouvez surcharger via les variables d’environnement `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.

### KPIs couverts
- Pièces en cours (tblstep.Active=1) + jauge d’avancement.
- Lead time : écart prévu/réel (tblfinorderpos).
- Ordres finis par jour (tblfinorder).
- TRS (dispo/perf/qualité) par ressource (tblmachinereport + tblfinstep).
- Taux d’occupation machine (Busy/total).
- Top erreurs & First Pass Yield (tblfinstep + tblmainterror/tblerrorcodes).
- Temps moyen d’arrêt (séquences ErrorL1/ErrorL2 dans tblmachinereport).
- Taux de remplissage des buffers (tblbufferpos).
- Énergie moyenne par étape (ElectricEnergy* dans tblfinstep).
- Aperçu Robotino (distance, durée, vitesse moyenne, puissance estimée) + carte des positions.

### Idées d’évolution (MI2/MI3)
- Relier Robotino aux ordres via timestamps pour expliquer les trajets.
- Heatmap des vitesses/arrêts Robotino et alertes batterie.
- Filtres par ressource/produit, export PDF, alerting TRS.
- Tests de robustesse sous charge (caches, agrégations matérialisées).
