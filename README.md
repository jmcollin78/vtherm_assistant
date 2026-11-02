# vtherm_assistant
An AI assistant to help you with your Versatile Thermostats

## Développement

Prérequis : Python 3.14 et une connexion réseau pour installer les dépendances.

```sh
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
python -m vtherm_assistant
```

L'interface de développement est accessible à l'adresse <http://127.0.0.1:8765/>.
Le projet est en cours de construction : la page est vide et aucune fonction de
conversation ou de configuration n'est encore disponible.

Sur un Mac Apple Silicon, utiliser la même architecture pour Python et ses
dépendances. Si le terminal fonctionne sous Rosetta (`uname -m` affiche
`x86_64`) mais que les dépendances sont en `arm64`, ouvrir un shell natif avec
`arch -arm64 /bin/bash` avant d'exécuter les commandes ci-dessus.

Le mode ingress est activé avec `VTHERM_DEPLOYMENT_MODE=ingress`. Il refuse les
connexions qui ne proviennent pas du Supervisor et ne considère pas l'identité
transmise comme une preuve des droits administrateur. Le lancement doit passer
par `python -m vtherm_assistant`, qui désactive l'interprétation des en-têtes
de proxy par le serveur afin de conserver l'adresse du client réseau réel.
