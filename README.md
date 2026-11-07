# vtherm_assistant
An AI assistant to help you with your Versatile Thermostats

## Développement

Prérequis : Python 3.14 et une connexion réseau pour installer les dépendances.

```sh
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m pytest -q --ignore=tests/test_frontend.py --ignore=tests/test_packaging.py
python -m pytest -q tests/test_frontend.py tests/test_packaging.py
python -m vtherm_assistant
```

La suite comprend des tests Chromium sur ordinateur et mobile. Pour les lancer
seuls : `python -m pytest -q tests/test_frontend.py`. Ils utilisent des services
simulés, y compris pour les parcours reliés au backend ; aucune clé réelle ni
installation HA n'est nécessaire.

Backend et navigateur s'exécutent dans deux processus pytest pour séparer
les boucles de Playwright synchrone et d'`asyncio.run()`. Tous les fichiers de
tests sont conservés. Les contrôles Docker nécessitent `VTHERM_TEST_IMAGE` et
une image construite ; voir le [guide de construction](docs/ha-app-build.md).

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

Prérequis : le venv ci-dessus, Homebrew installé et Home Assistant de test
accessible sur `http://127.0.0.1:8123`. La tâche du proxy installe Caddy via
Homebrew au premier lancement s'il est absent.

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

Une erreur `mcp.http stage=initialize http_status=404` signifie que l'URL MCP
attendue (`/api/mcp`) n'existe pas sur l'instance HA contactée. Vérifier que
l'intégration **Model Context Protocol Server** est installée et configurée,
et que `VTHERM_HA_INTERNAL_URL` pointe vers la bonne instance Home Assistant.

### Erreur 400 avec Home Assistant dans Docker

Si HA répond directement sur `http://127.0.0.1:8123`, mais renvoie
`400: Bad Request` via `https://localhost:8444`, y compris sur `/auth/authorize`,
vérifier les journaux HA. Sur l'installation de test, ils indiquaient :

```text
Received X-Forwarded-For header from an untrusted proxy 172.17.0.1
```

HA dans Docker voit ici Caddy comme `172.17.0.1`, et non `127.0.0.1`.
Cette adresse dépend du réseau Docker : utiliser celle indiquée dans les
journaux de sa propre installation, sans autoriser tout le sous-réseau.

1. Ouvrir **Paramètres > Système > Réseau > Serveur HTTP > Proxy inverse**.
2. Activer la confiance dans `X-Forwarded-For` et ajouter l'adresse observée
	aux **proxys de confiance** (`172.17.0.1` dans cet exemple).
3. Enregistrer : HA redémarre. Confirmer les nouveaux paramètres si demandé.
4. Vérifier que `https://localhost:8444` affiche HA, puis relancer
	**Se connecter** depuis l'assistant sur `https://localhost:8443`.

Ce refus intervient au niveau du proxy, avant OAuth. Il ne nécessite pas
d'ajouter l'URL de l'assistant aux origines CORS autorisées.

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

Le lancement ingress lit les options JSON de l'app dans `/data/options.json`
avant de charger le backend. L'option `ha_internal_url` est prioritaire sur
`VTHERM_HA_INTERNAL_URL` ; si elle est absente d'un objet d'options valide,
le défaut est `http://homeassistant:8123`. L'adresse doit être une base HTTP
ou HTTPS sans chemin, identifiants, paramètres ni fragment ; un port
personnalisé est accepté. Une configuration explicitement invalide ou un fichier
illisible bloque le lancement avec un message sans contenu brut des options.

Sous Supervisor, l'absence du fichier bloque également le lancement. Pour
les tests ingress hors Supervisor, un fichier absent conserve l'adresse fournie
par environnement, après validation, ou l'état non configuré si elle est absente.
Le mode autonome ne lit jamais ce fichier et conserve sa configuration OAuth.

Le jeton Supervisor sert à vérifier les droits de l'utilisateur auprès de Core,
pas à remplacer le jeton MCP. Chaque administrateur configure son jeton HA et
ses clés fournisseur dans l'interface ; ces secrets ne sont pas des options
globales du paquet. Avec une adresse interne HTTP, jetons et données circulent
en clair sur le réseau interne : n'utiliser qu'un réseau de confiance ou choisir
HTTPS, sans désactiver la vérification des certificats. Une instance Core avec
TLS ou port personnalisé nécessite une adresse adaptée.

Le backend refuse les connexions qui ne proviennent pas du Supervisor et
vérifie les droits de l'utilisateur auprès de Home Assistant. Le lancement
doit passer par `python -m vtherm_assistant`, qui désactive l'interprétation
des en-têtes de proxy pour conserver l'adresse du client réseau réel. Le
paquet d'installation HA OS n'est pas encore disponible.

La construction Linux, les dépendances figées et les essais avec volumes
temporaires sont décrits dans le [guide de construction](docs/ha-app-build.md).

L'interface est servie sous un préfixe variable, par exemple
`/api/hassio_ingress/<session>/`. Les ressources, dont le logo, et les appels
API utilisent des chemins relatifs pour rester dans ce préfixe. Aucun port
supplémentaire ni carte de tableau de bord n'est nécessaire. Un refus ingress
ne propose pas de connexion OAuth : vérifier la session HA et les droits
administrateur, sans contourner la vérification du backend.

Pour vérifier cette tranche avec des services simulés :

```sh
python -m pytest -q tests/test_app.py tests/test_ha_auth.py
python -m pytest -q tests/test_frontend.py
```

Les tests navigateur couvrent le préfixe ingress, le chargement du logo,
la configuration, la conversation et sa suppression sur ordinateur et mobile.
Le proxy de test retire le préfixe avant les routes internes. Les réponses
NDJSON y sont simulées et peuvent être livrées en un seul corps : ces tests
ne prouvent pas la progression réseau à travers le vrai Supervisor.

Lors de la validation sur HA OS, ouvrir l'app par ingress et vérifier que
plusieurs fragments de réponse apparaissent avant la fin de la requête.
Une réponse interrompue doit être signalée comme incomplète et pouvoir être
relancée. Ne pas activer `ingress_stream` pour résoudre un problème de réponses
progressives : cette option concerne les corps des requêtes entrantes.
Ne pas arrêter HA ou modifier le chauffage pour simuler une panne.

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

## Diagnostics

Les erreurs de l'application sont écrites dans le terminal
**VTherm: application locale**, au niveau `ERROR` ; les alertes MCP sont au
niveau `WARNING`. Après une modification du code, arrêter puis relancer cette
tâche pour charger les nouveaux diagnostics. Les journaux du proxy se trouvent
dans le terminal **VTherm: proxy HTTPS local**.

Le message de l'interface reste générique pour protéger les données. Le journal
conserve les métadonnées nécessaires au diagnostic, par exemple :

```text
operation=provider.generate stage=request error_type=AuthenticationError http_status=401 code=invalid_api_key category=authentication
operation=conversation.respond stage=stream error_type=AuthenticationError http_status=401 code=invalid_api_key category=authentication
```

La première ligne situe la cause ; la seconde indique où elle a interrompu la
conversation. Les étapes sont `load_conversation`, `prepare_agent` (modèle et
découverte MCP), `restore_context`, `stream`, `finalize` et `save_conversation`.
Le type d'exception dépend du SDK. Le statut ou le code vaut `unknown` lorsque
la bibliothèque ne fournit pas cette métadonnée reconnue.

Principaux cas à vérifier :

- `authentication`, HTTP `401`, `invalid_api_key` : clé du fournisseur refusée.
- `model_access`, `model_not_found` : identifiant du modèle ou droit d'accès.
- `quota`, `insufficient_quota` : crédits ou quota du compte fournisseur.
- `rate_limit`, HTTP `429` : limite de requêtes ; un `429` peut aussi signaler
	un quota insuffisant lorsque le code fournisseur le précise.
- `parameters` : paramètre de génération non accepté ; `context_limit` :
	contexte trop long.
- `operation=mcp.session`, `stage=authentication`, `missing_token` ou
	`permission` : jeton HA absent ou droits administrateur non vérifiés.
- `operation=mcp.http`, `stage=initialize`, HTTP `404` : vérifier que
	l'intégration MCP est installée sur l'instance ciblée ; `401` ou `403` :
	vérifier l'authentification et les droits. Le statut est enregistré avant
	sa transformation par le SDK ; une ligne `mcp.session` peut ensuite signaler
	une erreur de protocole avec un statut `unknown`.
- `no_allowed_tools` : MCP répond mais ne publie aucun outil reconnu par notre
	liste de lecture ; vérifier la version HA et l'exposition des entités.
- `tool_error` : un outil MCP a renvoyé un résultat en erreur ; seul son nom
	autorisé est journalisé, pas son contenu.
- `connection`, `timeout` ou `server` : connexion, délai ou service distant.

Les diagnostics ne recopient ni le message brut de l'exception, ni le corps
HTTP, ni les URL, en-têtes, questions ou résultats d'outils. Les codes inconnus
sont remplacés par `unknown`, pour ne pas exposer un contenu arbitraire ou un
fragment de clé. Le masquage des secrets et des transports reste actif ; ne
pas désactiver ces protections pour diagnostiquer une erreur.

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
