# Construction de l'app HA OS

## Base et resolution

La base est `python:3.14.10-slim-trixie`, figee par le digest multiarchitecture
`sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d`.
Sa revision upstream est `01dcc3d31fcd879f9af36e097bd96328a457f4bd`.
Les contraintes de release sont dans `requirements-ha.lock` ; elles couvrent
les dependances transitives Python et le backend setuptools de construction.
Les plages publiques de `pyproject.toml` restent inchangees.

Le paquet est installe depuis `pyproject.toml`, pas lance depuis une copie du
depot. Le contexte Docker exclut les venv, donnees locales, caches et fichiers
de planification. La couche finale n'inclut pas le repertoire `/build`.

L'image contient les inventaires dans `/usr/local/share/vtherm-assistant/` :

- `requirements-ha.lock` : contraintes utilisees pour la construction.
- `python.txt` : versions Python installees, y compris le paquet et pip.
- `debian.txt` : versions des paquets systeme de la base Debian.

## Validations locales

Le 2026-11-07, avec Docker 29.9.2 sur le Mac Apple Silicon de developpement :

| Plateforme | Construction | Imports application/ADK | HTML/PNG | Contraintes et pip check |
| --- | --- | --- | --- | --- |
| linux/arm64 | reussie | reussis | presents | valides |
| linux/amd64 | reussie | reussis | presents | valides |

Python observe : 3.14.10 ; paquet : 0.1.0. Le test amd64 utilise l'emulation
du moteur local. Aucun echec de construction apres verrouillage des dependances
n'a ete constate. Ce tableau ne certifie pas ingress, les droits Supervisor,
le streaming reel, les mises a jour ou la restauration sur HA OS.

## Construire et verifier

Depuis la racine, avec Docker/Buildx et un moteur capable d'executer les deux
architectures (emulation ou runners natifs) :

```sh
docker buildx build --platform linux/arm64,linux/amd64 --load -t vtherm-assistant:test .
VTHERM_TEST_IMAGE=vtherm-assistant:test python -m pytest -q -s tests/test_packaging.py
docker run --rm --platform linux/arm64 vtherm-assistant:test cat /usr/local/share/vtherm-assistant/python.txt
docker run --rm --platform linux/arm64 vtherm-assistant:test cat /usr/local/share/vtherm-assistant/debian.txt
```

Le chargement multiarchitecture exige un stockage d'images containerd recent.
Sur le Mac de developpement, remplacer `python` par `arch -arm64 .venv/bin/python`
dans les commandes Python. Sans `VTHERM_TEST_IMAGE`, les tests Docker sont ignores :
un pytest ordinaire ne constitue donc pas une preuve de construction Linux.

Les tests utilisent uniquement des identites et jetons factices, aucun port
hote et des volumes temporaires `vtherm-test-*`. Ils verifient les imports,
ressources et contraintes, le port interne 8099, le refus d'acces HTTP direct,
la reprise du volume, les modes `0700`/`0600`, les proprietaires, l'absence de
reparation automatique et l'arret gracieux par SIGTERM en moins de 10 secondes.
Ils relevent taille non compressee, memoire Docker et temps de demarrage.

## Compte et donnees

Le compte explicite est UID/GID `0:0`, stable entre versions, pour utiliser
le volume `/data` fourni par Supervisor sans chown ni ouverture des permissions.
Ce n'est pas une image non-root. Aucun privilege, socket Docker, montage HA,
materiel ou reseau hote supplementaire n'est demande par l'app.

Seul `/data/vtherm-assistant` contient les donnees applicatives. Il est cree
prive ; sa base SQLite appartient au meme UID. Un stockage mal protege est
refuse sans suppression, chown ou chmod automatique. Ne jamais reutiliser
les donnees personnelles du Mac pour les tests d'image. Les secrets restent
en clair dans SQLite et doivent etre proteges aussi dans les sauvegardes.

La commande est `python -m vtherm_assistant`, avec l'init du Supervisor pour
transmettre les signaux. Les tests utilisent `docker run --init` et aucun
S6/Bashio. Le fichier d'options absent des volumes de test utilise le parcours
de developpement ingress hors Supervisor ; le fichier reel est obligatoire
avec un jeton Supervisor. Les regressions de lecture d'options sont couvertes
par `tests/test_app.py`.

## Mesures de reference locales

Releve le 2026-11-07, moteur Docker local limite a 1.924 GiB :

| Plateforme | Taille non compressee (octets) | Memoire au demarrage | Demarrage |
| --- | --- | --- | --- |
| linux/arm64 | 596279769 | 144.1 MiB | 1.68 s |
| linux/amd64 | 576513482 | 141.9 MiB | 2.85 s |

Ces mesures correspondent au serveur sans inference ni connexion HA reelle,
pas a un budget garanti sur HA OS. Une conversation et un modele charges
peuvent augmenter la memoire. Le test amd64 est emule ; le temps n'est pas une
comparaison de performances entre materiels HA.

## Catalogue et CI

Le generateur ne copie que `repository.yaml` et les huit fichiers publics de
l'app, dont un seul `config.yaml`. Il ne copie ni sources Python, OpenSpec,
venv, base SQLite ni options personnelles. La sortie `dist/` est ignoree par
Git et un dossier existant est refuse plutot qu'efface ou remplace.

```sh
python scripts/package_ha_app.py --output dist/ha-app-release
```

La CI `ha-app.yml` execute les tests et construit les deux architectures avec
Buildx, QEMU et le stockage containerd pour le chargement multiarchitecture.
La syntaxe GitHub Actions est verifiee avec actionlint 1.7.7, image outil figee
par digest ; ce controle a aussi ete execute localement.
Les contraintes de release sont aussi appliquees aux tests. Elle prepare un
artefact `ha-app-unpublished`, sans login GHCR, droit d'ecriture, push d'image,
commit ou push de catalogue. Un push utilisateur des sources peut declencher
des validations, jamais une publication implicite.

Les suites backend et navigateur sont executees dans deux processus pytest.
Playwright synchrone garde une boucle active pendant sa session, incompatible
avec les tests backend utilisant `asyncio.run()` dans ce meme processus. Aucun
test n'est supprime : les fichiers exclus du premier processus sont tous
executes dans le second, avec les tests Docker actives.

```sh
python -m pytest -q --ignore=tests/test_frontend.py --ignore=tests/test_packaging.py
VTHERM_TEST_IMAGE=vtherm-assistant:test python -m pytest -q tests/test_frontend.py tests/test_packaging.py
openspec validate package-ha-os-app --strict
```

Bilan local du 2026-11-07, avec les commandes ci-dessus et les deux images
Docker construites : 203 tests backend reussis en 5.29 s et 80 tests navigateur,
packaging et Docker reussis en 80.39 s, soit 283 tests sans exclusion finale.
Actionlint et `openspec validate package-ha-os-app --strict` reussissent aussi.
Les avertissements de deprecation des dependances restent distincts des echecs.
La premiere execution en un seul processus a echoue sur le conflit de boucle
Playwright/asyncio ; les executions separees sont la procedure validee.

Ce bilan couvre les simulations d'authentification, mutations, isolation,
outils MCP interdits, secrets et erreurs fournisseur ; il ne prouve pas une
session Supervisor reelle ni une lecture ou restauration sur HA principal.
Le workflow a depuis ete pousse par l'utilisateur. L'API GitHub confirme
la reussite du [run 42423430156](https://github.com/jmcollin78/vtherm_assistant/actions/runs/42423430156)
sur la revision source `bcb01602992bdcd9aa9b4b92b0229dd7c645f644`.

## Release 0.1.1

Le 2026-11-08, la revision source
`93bddd921656a5a02c4c94d20cf2a5b18a7d0252` a ete validee par la
[CI 42464546539](https://github.com/jmcollin78/vtherm_assistant/actions/runs/42464546539).
Le helper de test attend maintenant le demarrage pendant au plus 120 secondes
au total, sans renouveler ce delai a chaque ligne de log ; la limite SIGTERM
reste de 10 secondes.

Cette release accepte les trois outils de lecture VTherm avec ou sans le
prefixe `assist__`. HA conserve les noms bruts lorsqu'une seule API LLM est
exposee et ajoute un espace de noms lorsqu'il fusionne plusieurs API.
Les commandes d'ecriture restent interdites et les schemas restent locaux.

L'image publique `ghcr.io/jmcollin78/vtherm-assistant:0.1.1` a pour digest :
`sha256:50806a00247a57e865dab6597702adb8708ec8171554a58be898caf3fc10d9a6`.
Les 12 tests Docker des images exactes arm64 et amd64 ont reussi avant
publication. L'index publie correspond a l'index teste ; les deux configurations
et les dix couches ont ete telechargees anonymement, avec tailles et SHA-256
verifies. Les labels version, source et revision correspondent a cette release.
Le digest public de `0.1.0` est inchange.

Le catalogue `ha-app` est publie au commit
`6e3d983e89f710d1bc1433c8fb32ad8409018719`, en conservant son historique.
Les neuf fichiers publics ont ete compares octet par octet au catalogue valide ;
seuls le manifeste de version et le changelog ont change. La mise a jour de
l'app et la lecture MCP reelle sur HA OS restent a verifier ; aucune
configuration HA n'a ete modifiee pendant cette publication.

### Etat de reprise au 2026-11-08

- Source : branche `main`, commit `93bddd921656a5a02c4c94d20cf2a5b18a7d0252`,
	synchronisee avec `origin/main`. Seul ce document reste modifie localement
	et non commite apres publication.
- Change `package-ha-os-app` : 21/25 taches terminees. Les taches 6.3 a 6.6
	restent ouvertes ; aucun archivage ni synchronisation des specs effectue.
- HA OS : installation `0.1.0`, sidebar et controle administrateur ingress
	confirmes. L'utilisateur confirme maintenant un essai de decouverte en `0.1.1`.
- L'utilisateur confirme une vraie liste et un diagnostic dans l'app locale.
	Sur HA OS en `0.1.1`, la lecture MCP est corroboree et la decouverte de
	douze VTherm est confirmee resolue. Un diagnostic est confirme coherent
	avec l'etat HA. L'utilisateur a clairement vu les douze entites arriver
	progressivement et confirme le streaming resolu sur le vrai ingress.
- Prochaine action pour 6.3 : relever les outils effectivement appeles et
	l'absence d'appel de commande pendant une conversation reelle.
	La conservation de la configuration et de la conversation reste a verifier.
- Ne pas ecraser les tags publics `0.1.0` ou `0.1.1`, modifier le chauffage,
	l'exposition globale ou HA/VTherm. Sauvegarde cold et restauration de l'app
	exigent chacune un accord distinct. Aucun jeton ne doit etre transmis en chat.

### Reprise de la validation 6.3 au 2026-11-08

Priorite precedente demandee par l'utilisateur : mettre le diagnostic du streaming
en pause et traiter la liste incomplete des VTherm (quatre presentes pour une
dizaine attendue). Cette pause initiale ne validait ni ne supprimait le critere
de streaming ; l'observation ulterieure des douze entites progressives le
valide maintenant (voir le bilan ci-dessous). Ne pas confondre inventaire de l'installation et
inventaire des entites accessibles via Assist ; le perimetre attendu incluant
eventuellement les entites non exposees reste a clarifier avant d'elargir les
acces ou de modifier l'exposition.

Le test MCP existant a ete renforce avec un resultat factice de dix VTherm :
le compte et toutes les entites traversent le client et l'outil ADK sans
troncature. La commande `arch -arm64 .venv/bin/python -m pytest -q
tests/test_ha_mcp.py -k accepts_assist_prefixed_vtherm_read_tools` passe avec
trois tests. Cela ne prouve ni le compte MCP reel sur HA ni l'exhaustivite de
la restitution du modele pendant l'essai utilisateur.

L'utilisateur rapporte une decouverte partielle en `0.1.1` sur HA OS : la
reponse presente quatre VTherm, alors que l'installation en contient davantage.
Elle qualifie sa source d'inventaire expose a Assist. Cette reponse seule ne
prouve ni le contenu brut du resultat MCP, ni les outils effectivement appeles,
ni l'absence d'appel de commande ou la progression avant la fin.

Le code officiel VTherm `10.6.3`, dans `_get_vtherm_entity_ids` de
`custom_components/versatile_thermostat/llm.py`, selectionne les entites
`climate` de ses config entries, presentes dans les etats HA et exposees a
l'assistant selon `async_should_expose`. `ListVThermsTool` retourne leur liste
et son compte sans limite de quatre. Le client MCP de l'assistant ne tronque
pas ce resultat. L'option `Expose all LLM APIs` ne supprime pas ce filtre
d'exposition des entites. L'utilisateur confirme qu'un VTherm manquant n'est
pas expose dans une premiere observation, puis corrige ce point apres
verification dans l'interface : cette entite est bien marquee exposee.
L'explication de son omission par une non-exposition n'est donc plus etablie.
L'utilisateur observe que les quatre entites retournees coincident avec un
meme etage ; cette correlation n'est pas encore une preuve de filtrage.

Le code de `ListVThermsTool` en `10.6.3` et le filtre `async_should_expose`
de HA `2026.10.4` ne selectionnent ni etage ni piece. Le schema local de
`list_vtherms` n'accepte aucun argument de filtrage ; `GetLiveContext` est un
outil distinct dont le schema local accepte `area`. Il reste a etablir lequel
est effectivement appele, ses arguments et le compte MCP reel, puis a comparer
son resultat avec la reponse du modele. Ni une reformulation de la reponse ni
le code upstream ne prouvent l'execution sur cette instance. Aucune exposition
globale, modification du chauffage ou mise a jour HA/VTherm n'est demandee.

Apres une demande ciblee de relecture avec `list_vtherms`, l'utilisateur
rapporte encore `count: 4` et les memes quatre entites. Le compte reste repris
d'une reponse du modele, pas d'une capture brute MCP. Le serveur officiel HA
`2026.10.4` utilise `assistant="conversation"` et renvoie les donnees d'outil
en JSON sans troncature ; aucun filtre d'etage n'est ajoute dans ce chemin.

Le test discriminant suivant est un appel direct au meme endpoint officiel
`/api/mcp` depuis la session navigateur HA, avec `tools/list` puis
`tools/call` pour le seul outil autorise `list_vtherms`. L'API frontend
`hass.callApi` de la version `20260930.5` accepte les en-tetes JSON requis
et reutilise l'authentification sans lecture ou affichage du jeton. Relever
uniquement le nom exact de l'outil, le compte et les entity_ids, sans copier
les en-tetes ou une archive reseau contenant des secrets.

Cet essai a maintenant ete execute par l'utilisateur. Le resultat direct
indique `tool: assist__versatile_thermostat__list_vtherms`, `count: 4` et les
memes quatre entites que dans la reponse conversationnelle. Cette capture
corrobore une lecture MCP reelle et etablit que l'omission n'est pas une
troncature par le modele pour cet appel. Les deux operations du script sont
`tools/list` et `tools/call` avec les arguments vides de l'outil de liste ;
aucune commande de chauffage ou modification d'exposition n'est demandee.

Le controle en lecture seule a ensuite compare une entite manquante et une
entite retournee avec `config/entity_registry/get_entries`, les options
d'exposition `conversation` et la presence dans les etats HA. Les deux sont
enregistrees, chargees, sur la plateforme `versatile_thermostat` et non
desactivees. L'entite manquante a toutefois `conversation.should_expose: false`
et aucun assistant dans `homeassistant/expose_entity/list` ; l'entite retournee
a `conversation.should_expose: true` et figure pour `conversation`.

Cette preuve directe etablit la cause de cette omission : la non-exposition
a Assist, malgre l'impression contraire lors de la verification dans
l'interface. Elle ne prouve pas que toutes les autres omissions ont la meme
cause. Aucun filtre d'etage ni correctif du serveur VTherm n'est justifie
pour ce cas.

L'utilisateur a ensuite trouve l'entite marquee non exposee dans le detail
du climate, menu des assistants vocaux, puis active son exposition a Assist.
Il confirme qu'elle apparait maintenant. Ce resultat corrobore le filtre
d'exposition comme cause de cette omission, sans correctif ni republication
de l'app. Il signale une divergence entre l'ecran general d'exposition et
le detail de l'entite ; un defaut d'interface HA ou un affichage non actualise
reste une hypothese, faute de reproduction documentee des deux vues avec
le meme filtre d'assistant.

Cette modification ciblee a ete effectuee par l'utilisateur, pas par l'agent.
La lecture MCP directe apres modification est maintenant confirmee : le
compte passe de quatre a cinq et l'entite de la chambre figure dans la liste.
La relation entre son exposition Assist et sa decouverte est donc corroboree
avant et apres modification. La decouverte des autres VTherm manquants et
leur exposition effective restaient alors a verifier ; le compte cinq ne
constituait pas une preuve d'inventaire complet de l'installation.
Aucune exposition globale ou commande de
chauffage n'a ete executee par l'agent ; l'exposition Assist peut aussi rendre
l'entite accessible aux autres usages d'Assist. La tache 6.3 reste ouverte.

L'utilisateur fournit ensuite un nouveau resultat avec `count: 12` et une
liste de douze entites climate. La decouverte n'est donc plus limitee aux
quatre, puis cinq entites initialement retournees. Aucun correctif de
decouverte ni republication de l'app n'a ete effectue par l'agent. Le detail
des modifications d'exposition ayant precede ce resultat n'est pas fourni ;
la preuve avant et apres pour l'entite comparee reste etablie. Le resultat
ne prouve pas a lui seul l'exhaustivite par rapport au registre HA, mais
l'utilisateur confirme ensuite que le probleme d'inventaire est resolu.
La decouverte est donc validee par son observation du resultat de douze
entites, sans comparaison automatique supplementaire au registre HA.
La tache 6.3 reste ouverte pour ses criteres encore non verifies ; le
streaming est ensuite confirme resolu par l'utilisateur (voir ci-dessous).

L'utilisateur a ensuite obtenu un diagnostic d'un VTherm deja retourne et
confirme sa coherence avec l'etat reel HA. La comparaison des donnees courantes
est donc corroboree par son observation. Il rapporte une attente assez longue,
puis une reponse semblant arriver d'un coup, sans certitude : la progression
avant la fin reste non prouvee. L'affirmation du modele selon laquelle aucune
commande n'a ete executee ne remplace pas une trace des outils appeles.

La recherche documentaire locale peut telecharger un sitemap puis jusqu'a
20 pages sequentiellement. Si cet outil est appele, il peut contribuer au delai
avant le texte. `ConversationResponse.accept` n'affiche pas les evenements
d'appel ou de retour d'outil, mais transmet les fragments textuels du modele.
Ces constats de code ne prouvent ni une consultation web pendant cet essai,
ni l'origine du delai, ni un tamponnage ingress. Un essai de texte long sans
outil permet de mieux distinguer l'attente des outils de la progression du
texte ; une reponse courte ou la seule presence d'un lien documentaire ne
suffit pas a trancher.

Lors de l'essai suivant, l'utilisateur a demande 30 phrases sans outil ni
consultation web. Sa premiere impression etait un affichage d'un coup apres
environ cinq secondes sur HA OS. Lors d'un nouvel essai par l'adresse HTTP
locale de HA, sans le reverse proxy Nginx externe, il observe plutot trois ou
quatre paquets d'affichage tres rapproches apres quelques secondes d'attente.
Il precise donc que la reponse semble arriver rapidement en plusieurs fois.

Cette observation corrige la conclusion preliminaire de streaming absent :
elle corrobore un affichage progressif rapide, sans etablir encore le moment
des fragments par rapport a la fin de la requete. Nginx n'est pas necessaire
pour reproduire ce comportement, sans que cela prouve l'absence de toute
contribution de ce proxy sur le parcours externe. L'origine du delai initial
et les outils effectivement appeles restent non verifies. Aucune configuration
Nginx ou HA n'a ete modifiee pour cet essai.

Un test temporel local ajoute dans `tests/test_conversations.py` bloque le
second fragment du fournisseur simule jusqu'a reception du premier message
ASGI `http.response.body`, marque `more_body: true`. Les quatre variantes
Gemini, OpenAI, Anthropic et Ollama, ainsi qu'une cinquieme variante OpenAI
`gpt-6-luna`, passent avec ADK, masquage et middleware ingress actifs ; la
reponse est ensuite finalisee et conservee sans duplication. L'utilisateur
confirme que son fournisseur reel est OpenAI et son modele `gpt-6-luna`.
Le test de cette configuration verifie `stream=True` et le parametre existant
`reasoning_effort="none"`, sans appel au fournisseur reel ni utilisation de
cle personnelle.

```sh
arch -arm64 .venv/bin/python -m pytest -q tests/test_conversations.py -k ingress_route_emits_first_fragment
```

Resultat : 5 tests passes. Cette preuve ASGI ne couvre ni le reseau Uvicorn,
ni le vrai fournisseur, ni le navigateur ou les proxies HA. Les deux parcours
reels releves sont HTTPS via Nginx local avec resolution vers l'IP publique,
puis HTTP direct vers HA sur le reseau local ; l'app reste derriere ingress
dans les deux cas. Aucun correctif de streaming ni nouvelle release n'est
presente comme valide sur HA OS.

L'utilisateur confirme ensuite avoir clairement vu les douze VTherm arriver
progressivement et demande de marquer le streaming comme resolu. Cette
observation dans la conversation HA OS en `0.1.1` valide le critere de
fragments visibles avant la fin sur le vrai ingress ; le diagnostic du
streaming n'est plus en pause et ne demande aucun correctif ni republication.
Il s'agit d'une preuve visuelle utilisateur, pas d'une capture reseau horodatee.
La decouverte et le streaming sont donc resolus. La tache 6.3 reste ouverte
pour la trace des outils effectivement appeles et l'absence d'appel de
commande dans la conversation reelle ; les simulations locales et les
appels MCP directs en lecture seule ne remplacent pas cette trace.

Le tableau affiche en texte est reproduit dans le frontend local : son rendu
Markdown ne prenait pas en charge les tables. Le correctif local ajoute les
tables, les cellules construites sans HTML brut et le defilement horizontal.
Le test de reproduction echoue avant le correctif sur ordinateur et mobile ;
apres correction, la commande suivante passe avec 12 tests :

```sh
arch -arm64 .venv/bin/python -m pytest -q tests/test_frontend.py -k 'markdown or conversation_stream or navigation_under_ingress'
```

Ces tests couvrent historique, reception de fragments et rechargement sous
ingress simule, pas une progression reseau sur HA OS. Le correctif n'est pas
publie ; les tags `0.1.0` et `0.1.1` restent inchanges. La tache 6.3 reste
ouverte, comme 6.4 a 6.6, soit 21/25 taches terminees.

## Release 0.1.0

Le 2026-11-08, apres accord explicite, l'image
`ghcr.io/jmcollin78/vtherm-assistant:0.1.0` a ete publiee puis rendue publique.
Digest de l'index multiarchitecture :
`sha256:1e706799da51a80d83cf39f32ed14123177d541978dc6be01dc0d5878fbeea8d`.

Les 12 tests Docker des images de release ont reussi. Les manifests arm64
et amd64 publies correspondent aux images testees ; les labels version,
source et revision sont verifies. Les pulls avec une configuration Docker
sans identifiants reussissent. Pour exclure un faux succes lie au cache local,
chaque configuration et chaque couche des deux plateformes a aussi ete
telechargee directement via le registre anonyme, avec taille et SHA-256 verifies.

Le catalogue a ensuite ete publie dans la branche `ha-app`, au commit
`5cc3de833d08c81c4f125d76be02ecad90384888`. L'acces public GitHub confirme
exactement les neuf fichiers attendus, identiques au catalogue valide ;
aucun fichier OpenSpec ou source applicative n'est distribue.
La branche source reste sur sa revision initiale ; les mises a jour locales
de documentation et du suivi OpenSpec ne sont pas commitees sur cette branche.

La distribution utilise uniquement la branche `ha-app`. Adresse a ajouter
dans la boutique, en conservant le suffixe :
`https://github.com/jmcollin78/vtherm_assistant#ha-app`.
Le parseur Git du Supervisor accepte ce suffixe de branche. Le chargement
sur l'instance HA principale est maintenant confirme par l'utilisateur et
ses captures du 2026-11-08 : le catalogue VTherm Assistant apps presente
uniquement Assistant VTherm, la fiche indique `0.1.0` et le stade experimental.
Aucune fausse app OpenSpec n'est visible dans ce catalogue.

Versions relevees par l'utilisateur :

| Composant | Version ou methode |
| --- | --- |
| Installation | Home Assistant OS |
| Core | 2026.10.4 |
| Supervisor | 2026.10.5 |
| Operating System | 18.4 |
| Interface utilisateur | 20260930.5 |
| Architecture du conteneur | amd64 |
| Versatile Thermostat | 10.6.3 |

L'architecture amd64 est declaree par l'app et dispose d'une image publique
testee. La version VTherm est confirmee par la capture utilisateur. L'accord
explicite d'ajout du catalogue et d'installation experimentale a ete donne.

Le 2026-11-08, l'utilisateur confirme l'installation reussie de `0.1.0`,
l'option `ha_internal_url` a `http://homeassistant:8123`, la presence de
l'icone dans la barre laterale et l'ouverture de la page de conversation.
Ces observations confirment le demarrage et l'acces par le vrai ingress.

Le controle administrateur est corrobore par le chemin serveur existant :
en ingress, `AccessMiddleware` protege toutes les routes, y compris la page
HTML et `GET /api/conversation`. Leur acces exige la provenance Supervisor,
une identite unique et un resultat positif de `verify_ingress_admin`, via
`ws://supervisor/core/websocket` et `config/auth/list`. L'ouverture reussie
confirme cette chaine pour le compte courant ; aucune trace reseau brute
n'a ete collectee et cela ne prouve pas encore le refus d'un autre compte.

Aucune mise a jour HA/VTherm, modification de chauffage ou d'exposition
d'entites n'a ete requise pour ce parcours. La lecture MCP, le streaming,
la persistance apres redemarrage/mise a jour, l'isolation reelle des comptes,
les erreurs et les essais de sauvegarde restent a verifier. Le stade reste
experimental ; ce releve ne certifie pas la compatibilite complete.

## Publication apres confirmation

Ces etapes sont un jalon distinct, pas une autorisation de les executer :

1. Faire confirmer le commit/push des modifications source pour rendre le
	workflow disponible sur GitHub, puis son execution. Attendre la reussite
	des tests et constructions sur cette revision ; ne pas publier en cas d'echec.
2. Verifier la coherence version paquet, label image, manifeste et changelog.
	Le tag d'image est immutable : ne jamais ecraser une version existante.
	Prouver l'absence d'un nouveau tag avant sa publication ; une erreur reseau
	ou d'authentification n'est pas une preuve d'absence.
3. Faire confirmer la publication de l'image dans
	`ghcr.io/jmcollin78/vtherm-assistant:<version>`. S'authentifier directement
	dans le terminal avec un compte autorise a ecrire ce package ; ne pas
	transmettre de jeton a l'assistant. Une CI de publication future exige
	`packages: write` et une approbation explicite, absents du workflow actuel.
4. Publier l'image pour les deux architectures, avant tout catalogue. Par
	exemple, uniquement apres accord et validation du nouveau tag ; `VERSION`
	doit contenir cette nouvelle version, jamais `0.1.0` deja publiee :

```sh
docker buildx build --platform linux/arm64,linux/amd64 --push -t "ghcr.io/jmcollin78/vtherm-assistant:${VERSION:?definir une nouvelle version validee}" .
```

5. Rendre le package GHCR public dans ses reglages. Avec une configuration
	Docker anonyme separee, verifier l'inspection et le telechargement de chaque
	architecture declaree ainsi que labels et ressources. Un succes avec le
	login du mainteneur ne prouve pas que Supervisor pourra telecharger l'image.
6. Actualiser le statut de publication du README/changelog, puis regenerer
	le catalogue dans une nouvelle sortie. Faire confirmer la creation/push
	de la branche `ha-app` avec son contenu seul, depuis un repertoire de travail
	separe ; ne pas changer de branche dans le worktree utilisateur ni y effacer
	des sources. Le droit `contents: write` est necessaire si cette publication
	Git est automatisee, mais il n'est pas accorde a la CI actuelle.
7. Verifier le tag deja disponible, la version du catalogue, son unique app et
	l'adresse de distribution avec Supervisor avant de documenter un lien
	d'installation effectif. Conserver l'etat experimental tant que les preuves
	reelles d'ingress, droits, streaming et restauration sont manquantes.

Pour chaque mise a jour : nouvelle version immutable, validation, sauvegarde
de l'app apres accord, image publique d'abord, catalogue ensuite. Aucun changement
du chauffage, Recorder, Core ou OS n'est inclus. Installation, mise a jour et
restauration sur HA principal demandent chacune leur confirmation appropriee.

Pour les publications suivantes, partir d'un clone de la branche `ha-app` afin
de conserver son historique. Generer un nouveau catalogue valide, actualiser
uniquement ses neuf fichiers publics puis pousser sans force. Ne pas fusionner
la branche source dans `ha-app`, ce qui reintroduirait les fichiers OpenSpec.