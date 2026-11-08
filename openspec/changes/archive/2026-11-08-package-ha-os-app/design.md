# Design

## Context

Voir `proposal.md` pour la motivation et `specs/ha-app-deployment/spec.md` pour le contrat de deploiement.

Le code possede deja deux modes. `__main__.main()` lance Uvicorn sur `0.0.0.0:8099` en ingress, sur `127.0.0.1:8765` en autonome, avec `proxy_headers=False`. `AccessMiddleware` verifie la provenance `172.30.32.2`, l'identite `X-Remote-User-Id`, les droits administrateur et la protection des mutations. `verify_ingress_admin` utilise `ws://supervisor/core/websocket` avec `SUPERVISOR_TOKEN` et `config/auth/list` ; cette chaine doit encore etre verifiee sur un vrai Supervisor.

Les appels frontend sont relatifs, mais le logo utilise `/brand/logo.png` et le test `test_frontend_is_served` exige actuellement ce chemin absolu. Les tests navigateur existants ne prouvent pas le fonctionnement sous le prefixe du vrai ingress ni sa progression reseau.

`create_app()` choisit `/data/vtherm-assistant` en ingress, mais n'initialise MCP que si l'adresse HA interne est fournie. MCP exige un jeton utilisateur distinct. Le paquet demande Python >=3.14, avec ADK, LiteLLM et MCP. SQLite impose proprietaire et permissions prives ; ses secrets ne sont pas chiffres par l'assistant. Le depot contient `openspec/config.yaml`, ce qui impose de ne pas publier tout le depot source comme catalogue d'apps.

## Goals / Non-Goals

**Goals:**

- Ajouter une couche de deploiement mince au-dessus du paquet existant et garder un seul exemplaire des sources applicatives.
- Separer construction locale, preparation de la distribution, publication et operations sur HA afin de ne pas confondre leurs autorisations ni leurs preuves.
- Rendre les erreurs de lancement et les refus ingress diagnostiquables sans ouvrir les routes privees.

**Non-Goals:**

- Introduire une integration HA, une carte, un reverse proxy interne ou une nouvelle orchestration IA.
- Modifier le schema fonctionnel des conversations, elargir les outils MCP ou utiliser le jeton Supervisor comme identifiant MCP de remplacement.
- Deplacer automatiquement les donnees ou secrets du Mac vers HA, ni garantir une migration future de schema non encore definie.

## Decisions

### Image unique construite depuis la racine source

Ajouter un `Dockerfile` et un `.dockerignore` a la racine. Le contexte de construction reste le depot source, le paquet est installe a partir de `pyproject.toml` avec ses fichiers frontend. Exclure venv, caches, `build`, fichiers de test local et donnees privees. L'image ne contient ni cles utilisateur ni configuration HA preexistante.

Le choix initial est une base officielle Python 3.14 slim Debian, plutot qu'Alpine : glibc favorise la disponibilite des wheels des dependances IA. Fixer sa revision et son digest apres verification de sa disponibilite sur les deux architectures. Figer la resolution des dependances de release et conserver un inventaire, sans modifier inutilement les plages du paquet.

Utiliser `python -m vtherm_assistant` comme commande du processus unique avec `init: true`. Ne pas ajouter S6 ou Bashio, qui impliqueraient une autre base et une configuration de supervision sans besoin etabli. Verifier import, installation des ressources, `SIGTERM` et proprietaire du stockage avec le compte d'execution stable choisi pour l'image. Ne pas annoncer un durcissement non teste.

Construire pour `linux/arm64` et `linux/amd64`, qui correspondent a `aarch64` et `amd64` dans HA. Le manifeste HA ne liste une architecture qu'apres construction et test de demarrage reussis. Une construction sous macOS ne remplace pas la validation Linux.

Alternative rejetee : compiler les dependances sur l'instance principale lors de l'installation. Une image preconstruite rend cette installation plus courte et permet d'executer exactement l'artefact teste.

### Metadonnees et configuration du paquet

Conserver les metadonnees source dans `apps/vtherm_assistant/`, avec `config.yaml`, documentation, changelog et traductions des options. Configurer `ingress: true`, `ingress_port: 8099`, `panel_admin: true`, `panel_title`, une icone MDI, `startup: application`, `boot: auto`, `stage: experimental`, `homeassistant_api: true` et `backup: cold`.

Ne declarer aucun port hote, `host_network`, montage de configuration HA, socket Docker, acces materiel, `hassio_api` ou role administrateur Supervisor. `homeassistant_api` donne toutefois un acces Core administrateur : ce n'est pas une permission techniquement limitee a la lecture. La liste blanche MCP et les controles applicatifs restent la barriere de lecture seule. Un eventuel watchdog TCP sur 8099 ne prouve que l'ecoute du processus ; ne pas utiliser une route HTTP privee qui repondrait 403 et provoquerait des redemarrages.

Ajouter l'option globale `ha_internal_url`, par defaut `http://homeassistant:8123`. Le lancement ingress lit `/data/options.json` avec un parseur JSON structure, valide l'option selon les regles d'adresse interne existantes, puis renseigne `VTHERM_HA_INTERNAL_URL` avant le chargement de l'app. Une option explicitement invalide ou un JSON corrompu refuse le lancement sans contenu brut dans le journal. Si le fichier d'options est absent hors Supervisor, conserver la configuration ingress explicite par environnement pour les tests et le developpement ; sous Supervisor, le fichier est attendu. Le mode autonome ne lit pas ce fichier.

HTTP interne reste reserve au reseau de confiance ; les jetons y circulent en clair. Une instance Core avec TLS ou port personnalise utilise l'option correspondante, sans `verify=False`. Ne pas substituer `http://supervisor/core/api` a cette adresse : la connexion MCP et sa verification administrateur ont des contrats distincts, non verifies via ce proxy.

Les modeles et secrets restent configures par utilisateur dans l'interface. Ne pas les dupliquer dans des options globales HA ni les placer dans les variables de construction. Ce choix preserve l'isolation actuelle plutot qu'introduire des secrets partages.

### Interface et confiance ingress

Corriger le logo en URL relative et actualiser son test. Ajouter un parcours navigateur sous `/api/hassio_ingress/<token>/` couvrant logo, configuration, conversation, nouvelle conversation et rechargement. Le proxy de test retire le prefixe avant d'atteindre les routes internes. Ne pas imposer un `root_path` dynamique si les URL relatives suffisent.

Conserver `proxy_headers=False` et la verification du client reseau reel. Les identifiants doivent provenir du Supervisor, jamais de parametres navigateur. La presence dans la barre laterale ne remplace pas la verification serveur des droits.

Adapter le retour de refus en ingress sans lien OAuth inexistant. Si une indication du mode est necessaire dans la page, elle est non sensible et determinee par le backend, sans route donnant acces a des donnees privees. Ne pas desserrer le middleware pour resoudre un probleme de presentation.

Le flux actuel est une reponse NDJSON progressive ; aucun proxy applicatif supplementaire ni tampon de reponse n'est ajoute. `ingress_stream` concerne les corps de requetes, pas les reponses progressives, et n'est pas requis ici. Verifier le progres via le vrai ingress en plus du navigateur simule, qui peut avoir reconstruit tout le corps avant de l'afficher.

### Stockage et sauvegardes

Reutiliser `/data/vtherm-assistant`, sans monter le repertoire HA. Creer le sous-repertoire avec le compte d'execution de l'image, en respectant `0700` pour le repertoire et `0600` pour la base. En cas de mauvais proprietaire ou permissions, refuser l'acces au lieu d'elargir les droits ou d'effacer la base. Tester un volume vide puis sa reutilisation apres changement de conteneur.

Choisir `backup: cold` pour une copie SQLite coherente : le Supervisor arrete brievement l'app pendant la sauvegarde. Une sauvegarde a chaud exigerait un mecanisme SQLite dedie, sans benefice necessaire pour ce premier lot. La documentation precise la presence des secrets et les protections attendues du volume et des sauvegardes. Une restauration de l'app ecrase ses donnees et demande un accord explicite distinct.

### Distribution propre et publication versionnee

Generer un catalogue de distribution dans un repertoire de sortie ignore, contenant `repository.yaml` et uniquement le dossier de l'app. Il est prepare pour une branche dediee `ha-app`, sans `openspec`, venv ni autres configurations de developpement. Ne pas deplacer OpenSpec pour satisfaire le scanner Supervisor et ne pas copier manuellement les sources applicatives dans le paquet de distribution.

Le catalogue reference une image publique GHCR multiarchitecture via `image`. Il n'a pas besoin de reconstruire le code sur HA. Reutiliser `brand/icon.png` et `brand/logo.png`. Donner aux options des descriptions en francais et anglais.

La CI construit depuis le depot source, teste, publie une image immuable dont le tag correspond a la version du manifeste, puis met a jour le catalogue. Maintenir la coherence avec la version du paquet Python et le changelog. Choisir Buildx ou les actions builder composables maintenues, pas le builder monolithique deprecie ni un nouveau `build.yaml`. La creation de branche, le push et la publication GHCR sont des actions separees qui exigent une demande ou confirmation explicite ; la generation locale peut etre testee sans elles.

### Validation et articulation avec le change initial

Reutiliser les tests backend, MCP, stockage et navigateur existants. Ajouter les checks du manifeste, de la generation de distribution, des options de lancement, du contenu de l'image et de son arret. Les tests existants de refus d'acces et `test_ingress_identity_does_not_supply_an_mcp_token` doivent rester valides.

Le nouveau change porte les criteres du paquet. Les exigences fonctionnelles et les fonctions historiques non livrees restent dans `add-vtherm-ai-assistant`. Sa tache 8.1 et les volets OS de 8.3 a 8.5 peuvent etre rapproches des preuves de ce lot, sans cloture automatique de la validation historique ni du parcours Container. Ne pas modifier les artefacts du change initial dans ce lot sans accord.

## Risks / Trade-offs

- [Wheels Linux/Python 3.14 indisponibles ou image trop volumineuse] -> Construire et tester les deux architectures avant annonce ; documenter taille et consommation au demarrage. Ne pas baisser le minimum Python pour masquer un echec.
- [Controle administrateur non accepte via le vrai proxy WebSocket] -> Verifier `config/auth/list` avec le jeton fourni avant de qualifier l'app utilisable ; refuser l'acces en cas d'echec, sans privilegier le compte sur la seule identite ingress.
- [Confusion jeton Core/Supervisor et jeton MCP utilisateur] -> Conserver les deux chemins et la liste blanche de lecture ; tester les secrets dans les erreurs et ne pas annoncer une delegation automatique.
- [TLS ou port Core differents du defaut] -> Option d'adresse validee et diagnostic sans secret ; aucun contournement de TLS.
- [Tests navigateur cachant un tampon de flux] -> Verification de fragments avant la fin via le vrai ingress ; ne pas se limiter a un test du contenu final.
- [Sauvegarde cold interrompant une conversation] -> Documenter l'interruption et choisir une periode sans conversation active ; restauration uniquement apres accord.
- [Unique instance HA principale disponible] -> Valider l'image et les tests simules avant installation, utiliser des lectures connues, ne pas arreter ni mettre a jour HA/VTherm et consigner les essais impossibles. Aucun test de panne ne doit couper HA principal.
- [Publication annoncant une image encore absente] -> Publier l'image avant le catalogue et ne jamais remplacer un tag deja distribue.

## Migration Plan

1. Construire et valider localement l'image, les options et le catalogue genere, sans exporter de secrets du Mac.
2. Apres accord sur la publication, rendre les images publiques et publier le catalogue experimental.
3. Relever versions et architecture de HA principal en lecture seule ; confirmer prerequisites et demander l'accord avant installation. Ne pas installer de mise a jour HA/VTherm ni modifier les entites exposees automatiquement.
4. Installer l'app, configurer les identifiants dans ses champs et verifier ingress, lectures et reprise apres redemarrage de l'app seulement. Deux utilisateurs reels sont testes uniquement si des comptes existent ; sinon la preuve d'isolation reste automatisee et cette limite est consignée.
5. Tester sauvegarde et restauration limitees a l'app seulement apres les accords correspondants ; sans ces accords, garder les criteres de restauration non verifies.
6. Pour abandonner le test, arreter l'app ; la desinstallation ou suppression de ses donnees requiert une confirmation et n'affecte pas VTherm. Revenir a une ancienne image seulement si son schema de donnees est compatible ; sinon utiliser une sauvegarde de l'app avec accord plutot qu'une restauration HA complete.

## Open Questions

- Les versions et architectures effectivement relevees satisfont-elles les cibles HA 2026.10 / VTherm 10.6.3 ? Ce releve qualifie la compatibilite et ne justifie pas une mise a jour implicite.
- Quels tags et digests Python 3.14 et quelles resolutions de dependances passent les checks Linux sur les deux architectures ? Les choisir a partir des constructions, sans annoncer leur verification dans ce design.
- Un second compte administrateur et l'autorisation de restauration seront-ils disponibles pour les essais reels ? A defaut, consigner les preuves manquantes plutot que les simuler comme acquises.