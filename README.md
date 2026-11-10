# MonAllPg

Supervision PostgreSQL en **une seule interface Grafana**, fusion de deux projets :

| Dossier | Projet d'origine | Rôle |
|---|---|---|
| [`meteo/`](meteo/README.md) | RT_Meteo_PG | **Météo temps réel** d'un parc d'instances : un soleil, un nuage, un orage ou une lune par instance, relevé léger toutes les minutes depuis un bastion, sans agent ni extension sur les instances. |
| [`monap/`](monap/README.md) | monAp_pg | **Analyse détaillée** d'une instance : parc, instance, macro, intermédiaire, micro (sessions, requêtes, plans, CPU et disque réels), capacity planning, seuils. |

## Première page : la météo multi-instance

Grafana s'ouvre sur la **synthèse Météo** : toutes les instances du parc, les plus mal en point en premier. C'est la page d'entrée ; de là, une barre de navigation commune (présente sur les 12 pages) mène à tout le reste.

```
                      ┌──────────────────────────────┐
  page d'accueil  ──► │ Météo : Synthèse (tuiles)    │ ◄─ clic sur une tuile ─┐
                      └──────────────┬───────────────┘                        │
        ┌────────────────────────────┼────────────────────────────┐           │
        ▼                            ▼                            ▼           │
 Météo : Liste             Météo : Détail d'une instance      pages monAp_pg  │
 (une ligne/instance)      (indicateurs, processus,           Parc · Instance · Macro ·
                            blocages, transactions)           Intermédiaire · Micro ·
                                    └───────────────────────► Capacity · Seuils
                                                              (+ détail session / requête)
```

- **Barre de navigation** (haut de chaque page) : `Météo : Synthèse`, `Météo : Liste`, `Météo : Détail`, `Parc`, `Instance`, `Macro`, `Intermédiaire`, `Micro`, `Capacity`, `Seuils`.
- **Du détail Météo vers monAp_pg** : le nom de l'instance est transmis aux pages monAp_pg. Il faut donc que `meteo.instance.nom` soit **identique** à `asemon.instances.name` pour la même instance (voir [docs/architecture.md](docs/architecture.md)).
- **De monAp_pg vers la Météo** : retour à la synthèse ou à la liste en un clic ; le détail Météo s'ouvre sur la première instance (la variable `instance` de monAp_pg est un identifiant, pas un nom).

## Démarrer

1. [docs/installation.md](docs/installation.md) : installation complète sur trois VM (bastion, pg01, pg02), commande par commande, avec la machine où la taper.
2. [docs/architecture.md](docs/architecture.md) : ce qui est partagé, ce qui est séparé, les choix de fusion.
3. Détails de chaque moitié : [meteo/docs/](meteo/docs/) et [monap/docs/](monap/docs/) (les chemins `sql/`, `scrutateur/`, `scripts/`… de ces documents sont relatifs à `meteo/` ou `monap/`).

## Contenu du dépôt

```
grafana/        installation unifiée : sources de données, dossiers de tableaux de bord, page d'accueil
meteo/          scrutateur Python, schéma `meteo`, tableaux de bord Météo, VM Hyper-V (3 machines), tests
monap/          collecteurs Python, schéma `asemon`, tableaux de bord monAp_pg, paquets Deploy/, scripts
tests/          cohérence de la fusion (navigation, sources de données, rôles)
docs/           documents propres à la fusion
```

## Tests

```bash
python3 -m unittest tests.test_fusion                       # fusion : navigation, datasources, accueil, rôles
cd meteo && python3 -m unittest discover -s tests -t .      # 74 tests du scrutateur et des tableaux Météo
```

## État

- **Validé en local** : JSON des 12 tableaux de bord, liens de navigation, cohérence des sources de données et de la page d'accueil, tests du scrutateur Météo (74).
- **Non validé sur machines virtuelles** : l'installation unifiée (`grafana/install.sh`), le passage du nom d'instance de la Météo vers monAp_pg (correspondance Grafana par texte d'option), le partage du rôle `grafana_ro` entre les deux bases. À contrôler lors du premier déploiement ; voir la section « Contrôles » de [docs/installation.md](docs/installation.md).

Licence MIT.
