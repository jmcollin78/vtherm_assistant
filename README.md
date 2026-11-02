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

## Identification

L'accès aux données et aux requêtes est réservé aux administrateurs Home
Assistant actifs. Les sessions autonomes sont conservées en mémoire et ne
survivent pas au redémarrage du backend.

### Home Assistant OS : ingress

Le mode ingress est activé avec `VTHERM_DEPLOYMENT_MODE=ingress`. Il nécessite
un lancement par le Supervisor, qui fournit `SUPERVISOR_TOKEN` au backend et
transmet l'identité de l'utilisateur. Ce jeton doit rester secret et ne doit
jamais être transmis au navigateur.

Le backend refuse les connexions qui ne proviennent pas du Supervisor et
vérifie les droits de l'utilisateur auprès de Home Assistant. Le lancement
doit passer par `python -m vtherm_assistant`, qui désactive l'interprétation
des en-têtes de proxy pour conserver l'adresse du client réseau réel. Le
paquet d'installation HA OS n'est pas encore disponible.

### Home Assistant Container : OAuth

Le mode autonome nécessite un proxy HTTPS devant le backend et une URL HTTPS
de Home Assistant accessible au navigateur. Renseigner les trois adresses de
base, sans chemin ni identifiants :

```sh
export VTHERM_APP_URL=https://assistant.example.org
export VTHERM_HA_BROWSER_URL=https://home.example.org
export VTHERM_HA_INTERNAL_URL=http://homeassistant:8123
python -m vtherm_assistant
```

Le proxy doit transmettre les requêtes à `127.0.0.1:8765`. L'adresse interne
peut utiliser HTTP ou HTTPS ; en HTTP, les jetons et les données circulent en
clair entre le backend et Home Assistant. Utiliser uniquement un réseau de
confiance ou choisir HTTPS pour ce lien également.

Le navigateur ouvre `/auth/login`, puis l'utilisateur se connecte et autorise
l'application auprès de Home Assistant. Le retour OAuth vérifie son identité
et ses droits ; les routes privées restent inaccessibles sans session
administrateur. Une déconnexion via `POST /auth/logout` invalide la session
locale et tente de révoquer le jeton auprès de Home Assistant. Si cette
révocation échoue, le message indique que la déconnexion locale a réussi mais
que la révocation HA est impossible.

Un accès refusé renvoie `403` et le message « Accès refusé ». Les parcours sont
actuellement couverts par des tests simulés, pas encore validés sur une
installation Home Assistant réelle. L'interface de connexion et le paquet
de déploiement autonome restent à réaliser.

## Données locales

La dernière conversation, son contexte et les identifiants enregistrés sont
conservés dans une base SQLite locale, séparément pour chaque utilisateur HA
vérifié. Le répertoire est privé (`0700`) et la base accessible uniquement au
compte du processus (`0600`) ; les secrets ne sont pas chiffrés dans la base.
Protéger également l'accès à la machine, au volume et aux sauvegardes.

Par défaut, le répertoire est `/data/vtherm-assistant` en mode ingress et
`~/.local/share/vtherm-assistant` en mode autonome. `VTHERM_DATA_DIR` permet
de choisir un autre répertoire persistant privé. Pour retirer toutes les
données locales de l'assistant, arrêter le backend puis supprimer ce seul
répertoire et ses éventuelles sauvegardes. Une nouvelle conversation efface
les messages et le contexte locaux de son utilisateur ; elle ne supprime pas
les clés et ne modifie ni Recorder ni la configuration de VTherm.

Les fournisseurs de modèles distants peuvent recevoir la conversation et les
données d'installation nécessaires pour répondre. Leur conservation dépend
de leur politique : un effacement local ne garantit pas leur suppression chez
ces fournisseurs.
