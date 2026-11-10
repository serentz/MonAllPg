"""Cohérence de la fusion monAp_pg + RT_Meteo_PG : une seule interface Grafana, la synthèse Météo en page d'accueil."""
import json
import pathlib
import re
import unittest

RACINE = pathlib.Path(__file__).resolve().parent.parent
METEO = RACINE / "meteo" / "grafana" / "dashboards"
MONAP = RACINE / "monap" / "grafana"
PROV = RACINE / "grafana" / "provisioning"

PAGES_METEO = ["meteo-synthese", "meteo-liste", "meteo-detail"]
PAGES_MONAP = ["asemon-fleet", "asemon-instance", "asemon-macro", "asemon-intermediate", "asemon-micro",
               "asemon-capacity", "asemon-thresholds"]
PAGES_FILLES = ["asemon-query", "asemon-session"]  # ouvertes depuis Macro/Intermédiaire/Micro


def charge():
    out = {}
    for p in list(METEO.glob("*.json")) + [q for q in MONAP.glob("asemon-*.json")]:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("uid"):
            out[d["uid"]] = d
    return out


class TestNavigation(unittest.TestCase):
    def setUp(self):
        self.dbs = charge()

    def test_toutes_les_pages_sont_presentes_avec_uid_unique(self):
        self.assertEqual(sorted(self.dbs), sorted(PAGES_METEO + PAGES_MONAP + PAGES_FILLES))

    def test_chaque_page_offre_la_meme_barre_de_navigation_complete(self):
        attendu = PAGES_METEO + PAGES_MONAP
        for uid, d in self.dbs.items():
            cibles = [re.fullmatch(r"/d/([a-z-]+)", l["url"]).group(1) for l in d["links"]]
            self.assertEqual(cibles, attendu, uid)

    def test_les_liens_pointent_vers_des_pages_existantes(self):
        for uid, d in self.dbs.items():
            for l in d["links"]:
                self.assertIn(l["url"][3:], self.dbs, uid)

    def test_les_variables_ne_sont_transmises_qu_a_un_domaine_compatible(self):
        # Météo : variable instance = NOM ; monAp : variable instance = IDENTIFIANT (texte = nom).
        for uid, d in self.dbs.items():
            for l in d["links"]:
                cible = l["url"][3:]
                if uid.startswith("asemon-") and cible.startswith("meteo-"):
                    self.assertFalse(l["includeVars"], f"{uid} -> {cible} : un identifiant n'est pas un nom")
                if uid.startswith("asemon-") and cible.startswith("asemon-"):
                    self.assertTrue(l["includeVars"], f"{uid} -> {cible}")
                if uid == "meteo-detail" and cible.startswith("asemon-"):
                    self.assertTrue(l["includeVars"], "le nom de l'instance doit suivre vers monAp_pg")

    def test_les_deux_variables_instance_gardent_leur_domaine(self):
        meteo = [v for v in self.dbs["meteo-detail"]["templating"]["list"] if v["name"] == "instance"][0]
        self.assertIn("SELECT nom FROM meteo.instance", meteo["query"])
        monap = [v for v in self.dbs["asemon-instance"]["templating"]["list"] if v["name"] == "instance"][0]
        self.assertIn("name AS __text, instance_id AS __value", monap["query"])


class TestSourcesDeDonnees(unittest.TestCase):
    def setUp(self):
        self.ds = (PROV / "datasources" / "monallpg.yaml").read_text(encoding="utf-8")

    def test_les_trois_sources_et_leurs_uid(self):
        for uid in ("meteo-pg", "asemon-monitoring", "asemon-seuils"):
            self.assertIn(f"uid: {uid}", self.ds)

    def test_aucun_mot_de_passe_en_clair(self):
        mots = re.findall(r"^\s+password:\s*(.+)$", self.ds, re.M)
        self.assertEqual(len(mots), 3)
        for m in mots:
            self.assertTrue(m.startswith("$__env{"), m)

    def test_la_variable_ds_monitoring_ne_voit_que_la_source_asemon(self):
        self.assertRegex(self.ds, r"name: ASEMON\n")
        for uid, d in charge().items():
            if uid.startswith("asemon-"):
                v = [x for x in d["templating"]["list"] if x["name"] == "DS_MONITORING"][0]
                self.assertEqual(v["regex"], "/^ASEMON$/", uid)

    def test_les_pages_meteo_utilisent_la_source_meteo(self):
        for uid in PAGES_METEO:
            self.assertIn('"uid": "meteo-pg"', json.dumps(charge()[uid]))

    def test_variables_d_environnement_documentees(self):
        env = (RACINE / "grafana" / "grafana-server.env.example").read_text(encoding="utf-8")
        for var in re.findall(r"\$__env\{(\w+)\}", self.ds):
            self.assertRegex(env, re.compile(rf"^{var}=$", re.M), var)
        self.assertNotRegex(env, re.compile(r"^\w*PWD=\S", re.M), "aucun mot de passe dans le modèle")


class TestAccueil(unittest.TestCase):
    def test_la_page_d_accueil_est_la_synthese_meteo(self):
        env = (RACINE / "grafana" / "grafana-server.env.example").read_text(encoding="utf-8")
        m = re.search(r"^GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=(.+)$", env, re.M)
        self.assertTrue(m)
        chemin = m.group(1).replace("/var/lib/grafana/dashboards/", "")
        self.assertEqual(chemin, "meteo/synthese.json")
        self.assertEqual(json.loads((METEO / "synthese.json").read_text(encoding="utf-8"))["uid"], "meteo-synthese")

    def test_providers_et_installateur_utilisent_les_memes_dossiers(self):
        prov = (PROV / "dashboards" / "monallpg.yaml").read_text(encoding="utf-8")
        inst = (RACINE / "grafana" / "install.sh").read_text(encoding="utf-8")
        for sous in ("meteo", "monap"):
            self.assertIn(f"path: /var/lib/grafana/dashboards/{sous}", prov)
            self.assertIn(f'"$DASH/{sous}/"', inst)
        self.assertTrue((RACINE / "meteo" / "images" / "iconnes" / "Soleil.png").is_file())


class TestRoles(unittest.TestCase):
    def test_grafana_ro_commun_sans_mot_de_passe_en_clair_cote_meteo(self):
        sql = (RACINE / "meteo" / "sql" / "stockage" / "002_roles.sql").read_text(encoding="utf-8")
        self.assertIn("PASSWORD :'pwd_grafana'", sql)

    def test_les_deux_projets_vivent_dans_des_bases_distinctes(self):
        self.assertIn("meteo", (RACINE / "meteo" / "sql" / "stockage" / "001_schema.sql").read_text(encoding="utf-8"))
        self.assertIn("database: meteo", (PROV / "datasources" / "monallpg.yaml").read_text(encoding="utf-8"))
        self.assertIn("database: monitoring", (PROV / "datasources" / "monallpg.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
