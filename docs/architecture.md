# Architecture de la fusion

## Ce qui est partagé, ce qui reste séparé

| Élément | Météo (`meteo/`) | monAp_pg (`monap/`) | Dans MonAllPg |
|---|---|---|---|
| Base PostgreSQL de stockage | `meteo` (schéma `meteo`) | `monitoring` (schéma `asemon`) | **deux bases distinctes**, sur la même instance PostgreSQL (pg01) ou sur deux |
| Alimentation | scrutateur Python sur le bastion, 1 requête / instance / 60 s, à distance | collecteur (15 s), échantillonneur (2 s) et parseur de journaux **sur** l'instance surveillée | inchangé : la Météo reste « légère » (rien à installer sur l'instance) ; monAp_pg ajoute son détail là où il est installé |
| Rôle de lecture Grafana | `grafana_ro` | `grafana_ro` | **même rôle, même mot de passe** si les deux bases sont sur le même cluster (rôle de cluster) |
| Rôle d'écriture | `scrutateur` | `collector_writer` | distincts, chacun limité à sa base |
| Grafana | uid `meteo-*`, source `meteo-pg` | uid `asemon-*`, source `ASEMON` (`asemon-monitoring`) et `ASEMON Seuils` | **une seule Grafana**, deux dossiers (« Météo », « monAp_pg »), page d'accueil = `meteo-synthese` |
| Provisioning | fichiers | script API (`grafana-provision.sh`) | **fichiers** (`grafana/provisioning/`) ; le script API de monAp_pg n'est pas utilisé |
| Plugins | `marcusolsson-dynamictext-panel` | `marcusolsson-dynamictext-panel`, `volkovlabs-form-panel` | les deux |

Les identifiants techniques de chaque projet ne sont pas renommés (schéma `asemon`, services `asemon-*`, `scrutateur`) : aucun script ni VM existants ne sont cassés.

## Pages et navigation

12 tableaux de bord, tous avec la même barre de liens (testé par `tests/test_fusion.py`) :

| Dossier Grafana | uid | Page |
|---|---|---|
| Météo | `meteo-synthese` | **Accueil** : tuiles soleil / nuage / orage / lune, pires états d'abord |
| Météo | `meteo-liste` | Une ligne par instance |
| Météo | `meteo-detail` | Indicateurs, seuils, processus, blocages, transactions d'une instance |
| monAp_pg | `asemon-fleet` | Parc |
| monAp_pg | `asemon-instance` | Instance |
| monAp_pg | `asemon-macro`, `-intermediate`, `-micro` | Macro, Intermédiaire, Micro |
| monAp_pg | `asemon-capacity`, `asemon-thresholds` | Capacity planning, Seuils |
| monAp_pg | `asemon-session`, `asemon-query` | Détail d'une session, d'une requête (ouvertes depuis Macro / Intermédiaire / Micro) |

## Deux variables `instance` qui ne veulent pas dire la même chose

- **Météo** : `instance` = **nom** (`SELECT nom FROM meteo.instance`).
- **monAp_pg** : `instance` = **identifiant** affiché sous forme de nom (`SELECT name AS __text, instance_id AS __value FROM asemon.instances`).

Conséquences, décidées et testées :

1. De la Météo (`meteo-detail`) vers monAp_pg, la variable est transmise (`includeVars`) : Grafana la rapproche du **texte** de l'option, donc du nom. **Condition : même nom dans `meteo.instance.nom` et `asemon.instances.name`.** Sinon la page monAp_pg s'ouvre sur sa première instance (sans erreur).
2. De monAp_pg vers la Météo, la variable n'est **pas** transmise (un identifiant n'est pas un nom).
3. Entre pages monAp_pg, la variable est transmise comme avant.

## Sources de données

La variable `DS_MONITORING` des pages monAp_pg porte maintenant `regex: /^ASEMON$/` : sans cela elle proposerait aussi `meteo` et `ASEMON Seuils`, toutes de type PostgreSQL. La source s'appelle donc obligatoirement **ASEMON** (c'est le cas dans `grafana/provisioning/datasources/monallpg.yaml`).

Les mots de passe des trois sources viennent de variables d'environnement du service `grafana-server` (modèle : `grafana/grafana-server.env.example`).

## Page d'accueil

`GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/var/lib/grafana/dashboards/meteo/synthese.json` dans `/etc/default/grafana-server` : la page d'accueil de l'organisation par défaut est la synthèse Météo. Un utilisateur peut toujours choisir une autre page d'accueil dans son profil.

## Impact sur les instances surveillées

Inchangé. La Météo n'ajoute qu'une lecture de `pg_stat_activity` par minute et par instance, sans extension. monAp_pg garde ses agents sur les seules instances où il est installé : on peut avoir 200 instances dans la Météo et 5 dans monAp_pg.
