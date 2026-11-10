# Installation de MonAllPg (3 VM)

Topologie de référence, celle de `meteo/infra/hyperv/create_vms.ps1` (réseau `192.168.50.0/24`, Ubuntu 24.04, compte `admin01`) :

| VM | Adresse | Reçoit |
|---|---|---|
| `bastion` | 192.168.50.10 | scrutateur Météo, **Grafana** (les deux jeux de pages) |
| `pg01` | 192.168.50.11 | PostgreSQL 17 : bases `monitoring` (monAp_pg) **et** `meteo` (Météo) |
| `pg02` | 192.168.50.21 | instance surveillée : login Météo (rien d'autre) + agents monAp_pg si on veut l'analyse détaillée |

> **Statut** : l'ordre ci-dessous assemble des étapes déjà validées séparément sur VM (Météo : `meteo/docs/scrutateur.md` ; monAp_pg : `monap/docs/`). L'assemblage lui-même n'a **pas** encore été déroulé de bout en bout : contrôler chaque étape (section « Contrôles »).

## Où taper quoi

| Où | Connexion | Invite |
|---|---|---|
| PowerShell (Windows) | menu Démarrer | `PS C:\...>` |
| bastion | `ssh admin01@192.168.50.10` | `admin01@bastion:~$` |
| pg01 | `ssh admin01@192.168.50.11` | `admin01@pg01:~$` |
| pg02 | `ssh admin01@192.168.50.21` | `admin01@pg02:~$` |

Chaque bloc est précédé de sa machine. Mots de passe à choisir (lettres, chiffres, `. _ % + = -` ; ni espace, ni apostrophe, ni antislash) :

| Nom | Sert à |
|---|---|
| `PWD_GRAFANA_RO` | rôle `grafana_ro`, **commun aux deux bases** (lecture seule, pour Grafana) |
| `PWD_SCRUTATEUR` | rôle `scrutateur` de la base `meteo` |
| `PWD_CIBLE` | login `scrutateur` de l'instance surveillée pg02 (membre de `pg_monitor`) |
| `PWD_COLLECTOR` | rôle `collector_writer` (monAp_pg → base `monitoring`) |
| `PWD_THRESHOLDS` | rôle `grafana_thresholds` (formulaire des seuils) |
| `PWD_ASEMON_COLLECT` | login `asemon_collect` de pg02 (agents monAp_pg) |

`grafana_ro` existe **une seule fois par cluster** : `PWD_GRAFANA_RO` doit être **la même valeur** dans l'installation monAp_pg (étape 2) et dans celle de la Météo (étape 3). La seconde remplace la première.

## 1. Machines virtuelles (PowerShell, sur Windows)

```powershell
cd <dossier de MonAllPg>
.\meteo\infra\hyperv\create_vms.ps1
.\meteo\infra\hyperv\check_vms.ps1
```

Détails et paramètres : `meteo/docs/installation_vm.md`. Le script de destruction n'est pas modifié par la fusion.

## 2. pg01 : repository monAp_pg (sur pg01)

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/serentz/MonAllPg.git
cd MonAllPg/monap
mkdir -p ~/pkg && tar xzf Deploy/monAp_pg_instance_monitoring.tgz -C ~/pkg
cd ~/pkg/monAp_pg_instance_monitoring
cp scripts/asemon.env.example scripts/asemon.env
nano scripts/asemon.env
```

Valeurs à renseigner dans `asemon.env` : `COLLECTOR_PASSWORD=PWD_COLLECTOR`, `GRAFANA_RO_PASSWORD=PWD_GRAFANA_RO`, `GRAFANA_THRESHOLDS_PASSWORD=PWD_THRESHOLDS`, `SUBNET=192.168.50.0/24`, `MONITORING_IP=192.168.50.11`. Laisser `GRAFANA_ADMIN_PASSWORD` **vide** : Grafana est installée par MonAllPg (étape 5), pas par le script API de monAp_pg.

```bash
sudo ./install.sh
sudo ./verify.sh
```

On utilise le **paquet** `monAp_pg_instance_monitoring` et non `monap/scripts/install-monitoring.sh` : ce dernier installerait aussi Grafana sur pg01.

## 3. pg01 : base Météo (sur pg01)

Toujours dans le clone `~/MonAllPg` :

```bash
cd ~/MonAllPg
sudo -u postgres createdb meteo
sudo -u postgres psql -d meteo -v ON_ERROR_STOP=1 -f meteo/sql/stockage/001_schema.sql
sudo -u postgres psql -d meteo -v ON_ERROR_STOP=1 \
  -v pwd_scrutateur='PWD_SCRUTATEUR' -v pwd_grafana='PWD_GRAFANA_RO' -f meteo/sql/stockage/002_roles.sql
echo "host meteo scrutateur 192.168.50.10/32 scram-sha-256" | sudo tee -a /etc/postgresql/17/main/pg_hba.conf
echo "host meteo grafana_ro  192.168.50.10/32 scram-sha-256" | sudo tee -a /etc/postgresql/17/main/pg_hba.conf
sudo systemctl reload postgresql@17-main
```

`listen_addresses` a déjà été ouvert à l'étape 2.

## 4. pg02 : instance surveillée

**4a. Login de la Météo (sur pg02)** : suffisant pour la Météo.

```bash
sudo -u postgres psql
```

```sql
CREATE ROLE scrutateur LOGIN PASSWORD 'PWD_CIBLE';
GRANT pg_monitor TO scrutateur;
```

```bash
echo "listen_addresses = '*'" | sudo tee /etc/postgresql/17/main/conf.d/meteo.conf
echo "host all scrutateur 192.168.50.10/32 scram-sha-256" | sudo tee -a /etc/postgresql/17/main/pg_hba.conf
sudo systemctl restart postgresql@17-main
```

(Adapter `17` à la version installée sur pg02.)

**4b. Agents monAp_pg (sur pg02)** : facultatif, pour l'analyse détaillée de cette instance.

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/serentz/MonAllPg.git
mkdir -p ~/pkg && tar xzf MonAllPg/monap/Deploy/monAp_pg_instance_cible.tgz -C ~/pkg
cd ~/pkg/monAp_pg_instance_cible
cp scripts/asemon.env.example scripts/asemon.env
nano scripts/asemon.env
```

Renseigner `COLLECTOR_PASSWORD=PWD_COLLECTOR`, `ASEMON_COLLECT_PASSWORD=PWD_ASEMON_COLLECT`, `MONITORING_IP=192.168.50.11`, `INSTANCE_NAME=pg02`, `SERVICE_USER=admin01`, puis `sudo ./install.sh` et `sudo ./verify.sh` (procédure complète : `monap/docs/02-VM-Cible.md`).

**`INSTANCE_NAME` doit être écrit exactement comme le `nom` déclaré à l'étape 6** : c'est lui qui relie la Météo et monAp_pg.

## 5. bastion : scrutateur et Grafana (sur le bastion)

Scrutateur :

```bash
sudo apt update && sudo apt install -y git python3-venv
git clone https://github.com/serentz/MonAllPg.git
cd MonAllPg/meteo
sudo useradd --system --home-dir /opt/scrutateur --shell /usr/sbin/nologin scrutateur
sudo mkdir -p /opt/scrutateur/app /etc/scrutateur
sudo cp -r scrutateur /opt/scrutateur/app/
sudo python3 -m venv /opt/scrutateur/venv
sudo /opt/scrutateur/venv/bin/pip install -r /opt/scrutateur/app/scrutateur/requirements.txt
sudo install -m 0640 -o root -g scrutateur scrutateur/deploy/scrutateur.env.example /etc/scrutateur/scrutateur.env
sudo install -m 0644 scrutateur/deploy/scrutateur.service /etc/systemd/system/scrutateur.service
sudo systemctl daemon-reload
sudo nano /etc/scrutateur/scrutateur.env
```

Dans ce fichier : `SCRUTATEUR_STOCKAGE_DSN=postgresql://scrutateur:PWD_SCRUTATEUR@pg01:5432/meteo`.

Grafana ≥ 10.4 (dépôt apt officiel : https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/), puis :

```bash
sudo apt install -y grafana
sudo grafana cli plugins install marcusolsson-dynamictext-panel
sudo grafana cli plugins install volkovlabs-form-panel
cd ~/MonAllPg
sudo install -m 0640 -o root -g grafana grafana/grafana-server.env.example /etc/default/grafana-server
sudo nano /etc/default/grafana-server
```

Renseigner `METEO_GRAFANA_PWD=PWD_GRAFANA_RO`, `ASEMON_GRAFANA_RO_PWD=PWD_GRAFANA_RO`, `ASEMON_GRAFANA_THRESHOLDS_PWD=PWD_THRESHOLDS` (laisser la ligne `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH`). Puis :

```bash
sudo ./grafana/install.sh
```

Le script copie les 12 tableaux de bord (dossiers « Météo » et « monAp_pg »), les trois sources de données, les icônes, et redémarre Grafana. Il est rejouable. Sous RHEL 8.10 : `meteo/docs/installation_rhel8.md` (SELinux : `restorecon` sur `/var/lib/grafana/dashboards` et `/usr/share/grafana/public/img/meteo`).

## 6. Déclarer l'instance et démarrer (pg01, puis bastion)

Sur **pg01**, base Météo :

```bash
sudo -u postgres psql -d meteo
```

```sql
INSERT INTO meteo.instance (nom, login, password, host, port, base)
VALUES ('pg02', 'scrutateur', 'PWD_CIBLE', '192.168.50.21', 5432, 'postgres');
```

Si l'étape 4b a été faite, vérifier que `SELECT name FROM asemon.instances` (base `monitoring`) donne **le même nom** `pg02`.

Sur le **bastion** :

```bash
sudo -u scrutateur bash -c 'set -a; . /etc/scrutateur/scrutateur.env; set +a; cd /opt/scrutateur/app && /opt/scrutateur/venv/bin/python -m scrutateur --tester pg02'
sudo systemctl enable --now scrutateur
```

## 7. Ouvrir Grafana

`http://192.168.50.10:3000` (admin / admin à la première connexion, à changer). **La première page est la synthèse Météo.** La barre de liens en haut mène aux 11 autres pages.

## Contrôles (à faire au premier déploiement)

1. Accueil = tuiles Météo (sinon : `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH` absent de `/etc/default/grafana-server`, ou Grafana non redémarrée).
2. *Connections → Data sources* : `meteo`, `ASEMON`, `ASEMON Seuils`, chacune *Save & test* verte. Une erreur d'authentification vient du mot de passe de `/etc/default/grafana-server` ou d'une ligne `pg_hba.conf` manquante.
3. Dans « monAp_pg », la liste déroulante de source de données ne propose que `ASEMON`.
4. Météo : Détail → lien `Instance` : la page monAp_pg doit s'ouvrir **sur la même instance**. Si elle s'ouvre sur la première de la liste, le nom diffère entre `meteo.instance.nom` et `asemon.instances.name`, ou la version de Grafana ne rapproche pas par texte : le lien reste utilisable, la sélection se fait à la main.
5. `sudo journalctl -u grafana-server -n 50 --no-pager` sans erreur de provisioning (`datasource ... already exists` indique un ancien `meteo.yaml` : `grafana/install.sh` le supprime).

## Dépannage

| Symptôme | Cause probable |
|---|---|
| Tuiles Météo vides | scrutateur arrêté (`systemctl status scrutateur`), ou `meteo.instance` vide |
| `password authentication failed for user "grafana_ro"` sur une seule base | `PWD_GRAFANA_RO` différent entre l'étape 2 et l'étape 3 : refaire `002_roles.sql` avec la valeur de l'étape 2 |
| Pages monAp_pg : « Datasource ${DS_MONITORING} was not found » | la source ne s'appelle pas exactement `ASEMON` |
| Page Seuils en lecture seule | `ASEMON_GRAFANA_THRESHOLDS_PWD` vide ou `GRAFANA_THRESHOLDS_PASSWORD` vide à l'étape 2 |

Autres cas : `meteo/docs/scrutateur.md` (dépannage Météo) et `monap/docs/` (guide pas à pas, dépannage monAp_pg).
