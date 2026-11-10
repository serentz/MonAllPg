#!/usr/bin/env bash
# MonAllPg : installe les deux jeux de tableaux de bord, le provisioning et les icônes sur la VM Grafana (bastion).
# Prérequis : Grafana >= 10.4 installé (apt), plugins marcusolsson-dynamictext-panel et volkovlabs-form-panel.
# Usage : sudo ./grafana/install.sh   (depuis la racine du dépôt cloné)
set -euo pipefail
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(cd "$ICI/.." && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "À lancer avec sudo." >&2; exit 1; }

GRAFANA_ETC=/etc/grafana
DASH=/var/lib/grafana/dashboards
install -d -m 0755 "$DASH/meteo" "$DASH/monap" "$GRAFANA_ETC/provisioning/datasources" "$GRAFANA_ETC/provisioning/dashboards"

install -m 0644 "$RACINE"/meteo/grafana/dashboards/*.json "$DASH/meteo/"
install -m 0644 "$RACINE"/monap/grafana/asemon-*.json "$DASH/monap/"
rm -f "$DASH/monap/asemon-dashboard.json"   # ancien tableau de bord sans uid, remplacé par les pages Macro/Intermédiaire/Micro
install -m 0644 "$ICI/provisioning/datasources/monallpg.yaml" "$GRAFANA_ETC/provisioning/datasources/monallpg.yaml"
install -m 0644 "$ICI/provisioning/dashboards/monallpg.yaml"  "$GRAFANA_ETC/provisioning/dashboards/monallpg.yaml"
# Les anciens fichiers du seul projet Météo feraient doublon (même uid de source de données).
rm -f "$GRAFANA_ETC/provisioning/datasources/meteo.yaml" "$GRAFANA_ETC/provisioning/dashboards/meteo.yaml"

# Icônes de la météo
IMG=/usr/share/grafana/public/img/meteo
install -d -m 0755 "$IMG"
install -m 0644 "$RACINE"/meteo/images/iconnes/*.png "$IMG/"

for p in marcusolsson-dynamictext-panel volkovlabs-form-panel; do
    [ -d "/var/lib/grafana/plugins/$p" ] || echo "ATTENTION : plugin $p absent (grafana cli plugins install $p)." >&2
done
if [ ! -s /etc/default/grafana-server ] || ! grep -q '^METEO_GRAFANA_PWD=.' /etc/default/grafana-server; then
    echo "ATTENTION : /etc/default/grafana-server n'est pas renseigné (modèle : grafana/grafana-server.env.example)." >&2
fi
systemctl restart grafana-server
echo "Terminé. Ouvrir http://<bastion>:3000 : la première page est la synthèse Météo."
