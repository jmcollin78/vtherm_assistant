# vtherm_assistant
An AI assistant to help you with your Versatile Thermostats

## Développement

Prérequis : Python 3.14 et une connexion réseau pour installer les dépendances.

```sh
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m pytest -q
python -m vtherm_assistant
```

La suite comprend des tests Chromium sur ordinateur et mobile. Pour les lancer
seuls : `python -m pytest -q tests/test_frontend.py`. Ils utilisent des services
simulés, y compris pour les parcours reliés au backend ; aucune clé réelle ni
installation HA n'est nécessaire.

L'interface de développement est accessible à l'adresse <http://127.0.0.1:8765/>.
Le projet est en cours de construction. Les parcours authentifiés nécessitent
la configuration Home Assistant décrite ci-dessous ; les fournisseurs et MCP
n'ont été testés qu'avec des services simulés.

Sur un Mac Apple Silicon, utiliser la même architecture pour Python et ses
dépendances. Si le terminal fonctionne sous Rosetta (`uname -m` affiche
`x86_64`) mais que les dépendances sont en `arm64`, ouvrir un shell natif avec
`arch -arm64 /bin/bash` avant d'exécuter les commandes ci-dessus.

## Test local avec Home Assistant

Ce parcours utilise les vrais services HA, MCP et fournisseur de modèle,
contrairement aux tests automatisés qui les simulent. Aucune exposition à
Internet n'est nécessaire ; un fournisseur distant nécessite néanmoins une
connexion sortante et peut recevoir les données utilisées pour répondre.

### Préparer l'instance de test

1. Démarrer Home Assistant sur `http://127.0.0.1:8123` et créer un compte
	administrateur de test.
2. Installer VTherm et configurer au moins un thermostat avec des capteurs et
	un actionneur simulés, sans équipement de chauffage réel.
3. Ajouter l'intégration **Model Context Protocol Server** depuis
	**Paramètres > Appareils et services**. Dans ses options, rendre accessibles
	les API LLM Home Assistant et VTherm, et exposer les entités de test à Assist.
4. Depuis le profil de l'administrateur, créer un jeton longue durée pour les
	appels MCP. Ce jeton est distinct de la session OAuth de l'interface.
5. Préparer un modèle et sa clé fournisseur, ou un serveur Ollama compatible
	avec les appels d'outils. Noter les versions de HA, VTherm et le modèle testé.

### Lancement local depuis VS Code

Prérequis : le venv ci-dessus, Caddy (`rtk proxy brew install caddy` sur macOS)
et Home Assistant de test accessible sur `http://127.0.0.1:8123`.

Dans `Cmd+P`, saisir `task VTherm: demarrer en local (HTTPS)` puis Entrée.
Cette tâche lance le proxy Caddy et l'application avec les paramètres OAuth
locaux, dans deux terminaux dédiés :

- Assistant : `https://localhost:8443`, vers le backend `127.0.0.1:8765`.
- Home Assistant : `https://localhost:8444`, vers `127.0.0.1:8123`.
- Stockage de test séparé : `~/.local/share/vtherm-assistant-realtest`.

Au premier lancement, exécuter également depuis `Cmd+P` la tâche
`task VTherm: approuver le certificat local`. Elle nécessite que le proxy
soit démarré ; macOS peut demander une autorisation ou un mot de passe à saisir
directement dans le terminal. Cette action ajoute l'autorité locale de Caddy
au magasin de confiance ; elle n'est jamais exécutée automatiquement.
Ouvrir ensuite `https://localhost:8443`.

Home Assistant doit accepter le proxy dans ses réglages réseau
(`Trust X-Forwarded-For` et `Trusted proxies`, avec l'adresse du proxy telle
que HA la voit). Configurer également son URL navigateur avec
`https://localhost:8444`. Ne pas exposer les ports de test à Internet.
L'intégration MCP, VTherm et les identifiants restent à configurer dans HA
et dans l'assistant ; les tâches ne contiennent aucun secret.

Pour arrêter les deux processus, utiliser `Tasks: Terminate Task` depuis
la palette de commandes et arrêter les deux tâches enfants. Le lancement
applicatif utilise le Python ARM64 du venv sur macOS Apple Silicon.

### Vérifier le fonctionnement

1. Ouvrir `https://localhost:8443`, sélectionner **Se connecter** et autoriser
	l'application avec le compte administrateur HA de test.
2. Dans les paramètres de l'assistant, enregistrer le fournisseur, le modèle,
	sa clé éventuelle et le jeton HA. Saisir les secrets uniquement dans les
	champs prévus, jamais dans la conversation ou dans les fichiers du dépôt.
3. Demander « Quels thermostats sont disponibles ? », puis l'état et un
	diagnostic d'un thermostat précis. Comparer les résultats aux entités HA.
4. Modifier une donnée simulée dans HA et redemander l'état actuel : la réponse
	doit refléter la nouvelle valeur, pas seulement la conversation passée.
5. Arrêter et relancer l'application, se reconnecter et vérifier la reprise
	de la conversation. **Nouvelle conversation** doit effacer les messages
	et le contexte, sans supprimer les identifiants enregistrés.
6. Vérifier également le refus d'un compte non administrateur et le message
	d'erreur lorsque HA est indisponible, puis la possibilité de réessayer.

Un avertissement de certificat nécessite d'approuver l'autorité locale, sans
désactiver les vérifications HTTPS. Une erreur `502` sur le proxy HA indique
de vérifier le service sur le port 8123 ; un refus de proxy côté HA nécessite
de vérifier ses réglages de confiance. Des outils VTherm absents nécessitent
de vérifier les versions installées, les API MCP sélectionnées et l'exposition
des entités.

Ce parcours ne garantit pas encore la compatibilité des versions testées :
consigner les résultats et les éventuels écarts. L'historique détaillé dépend
d'un outil encore à réaliser ; la limitation du contexte reste à compléter.
Commencer avec des conversations courtes et l'installation de test isolée.

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
installation Home Assistant réelle. L'interface de connexion reste à vérifier
sur cette installation ; le paquet de déploiement autonome reste à réaliser.

## Données locales

La dernière conversation, son contexte et les identifiants enregistrés sont
conservés dans une base SQLite locale, séparément pour chaque utilisateur HA
vérifié. Le répertoire est privé (`0700`) et la base accessible uniquement au
compte du processus (`0600`) ; les secrets ne sont pas chiffrés dans la base.
Protéger également l'accès à la machine, au volume et aux sauvegardes.

Le contexte sauvegardé comprend les échanges ADK et les résultats des outils
effectivement appelés, après masquage des secrets et sans les fragments partiels
ni les parties de raisonnement interne. Ces résultats sont des observations
passées, pas une preuve de l'état actuel ; l'assistant doit relire les données
pour répondre sur le présent. La limitation selon la capacité du modèle reste
à compléter ; la borne actuelle sur les messages ne borne pas les résultats
d'outils (tâche OpenSpec 4.7).

Les parcours authentifiés masquent les secrets connus dans les journaux et les
traces d'erreur. Pendant les échanges sensibles, le contenu des journaux des
transports HTTP, OAuth, WebSocket et MCP est remplacé par un message masqué,
y compris pour les jetons nouvellement reçus. Le lancement documenté désactive
les journaux d'accès HTTP afin de ne pas y conserver les codes de retour OAuth.

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

## Accès MCP en développement

Le client utilise uniquement le serveur MCP officiel à l'adresse
`VTHERM_HA_INTERNAL_URL/api/mcp`. En mode ingress, définir également
`VTHERM_HA_INTERNAL_URL` ; chaque utilisateur doit enregistrer séparément un
jeton Home Assistant administrateur. L'identité ingress ne fournit pas ce jeton.
Le client vérifie les droits du jeton avant chaque connexion.

Les outils accessibles sont limités à `homeassistant__GetLiveContext`,
`versatile_thermostat__list_vtherms`, `versatile_thermostat__get_status` et
`versatile_thermostat__diagnose`. Les implémentations ont été examinées dans
les sources de [Home Assistant 2026.10.0](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/homeassistant/llm.py)
et de [VTherm 10.6.3](https://github.com/jmcollin78/versatile_thermostat/blob/10.6.3/custom_components/versatile_thermostat/llm.py),
respectivement. Leur disponibilité et leur comportement réel restent à vérifier
sur chaque installation et version. Les commandes et outils inconnus sont refusés.

Ces sources décrivent un contexte des entités exposées à Assist, une liste de
VTherm, leur état actuel et un diagnostic contenant des sections de leurs
attributs. Le contexte HA ne couvre pas les scripts et calendriers ; les
dépendances ne sont accessibles que si les outils et l'exposition les rendent
disponibles. Aucun outil d'historique n'est fourni par VTherm 10.6.3 ; son
[contrat proposé](docs/contrat-historique-mcp.md) reste à réaliser et vérifier.
La conversation utilise ces outils via ADK et reprend les échanges récents de
l'utilisateur. Les essais actuels reposent sur des services simulés : le
fonctionnement avec les installations et fournisseurs réels reste à vérifier.
