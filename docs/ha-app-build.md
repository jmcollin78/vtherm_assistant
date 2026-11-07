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
Le workflow n'a pas encore ete pousse ni execute sur GitHub.

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
	exemple, uniquement apres accord et validation du nouveau tag :

```sh
docker buildx build --platform linux/arm64,linux/amd64 --push -t ghcr.io/jmcollin78/vtherm-assistant:0.1.0 .
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