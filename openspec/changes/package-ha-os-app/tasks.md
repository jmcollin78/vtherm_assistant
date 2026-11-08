# Tasks

Le contrat est dans `specs/ha-app-deployment/spec.md` et les choix techniques dans `design.md`. Les groupes 1 et 2 peuvent avancer independamment de la construction du groupe 3 ; le groupe 4 depend de 2 et 3, la distribution de 3 et 4, puis les essais reels de tous les groupes precedents.

La creation de ces artefacts n'autorise pas un push, une publication ou une operation sur HA. Ne pas cocher un essai reel sans preuve ; une autorisation ou un environnement manquant laisse la tache ouverte avec une limite explicite. Ne pas modifier les artefacts du change initial sans accord.

## 1. Interface et controles ingress

- [x] 1.1 Corriger le logo absolu dans `src/vtherm_assistant/frontend/index.html` et l'assertion de `test_frontend_is_served` ; verifier le chargement PNG et le test backend existant avec le nouveau chemin relatif.
- [x] 1.2 Ajouter dans `tests/test_frontend.py` un parcours sous un prefixe ingress simule avec retrait du prefixe avant les routes internes ; verifier logo, configuration, question, nouvelle conversation, rechargement et absence de requete applicative hors du prefixe sur ordinateur et mobile.
- [x] 1.3 Adapter le refus d'acces ingress pour ne pas proposer un lien OAuth inexistant, sans ouvrir les routes privees ; verifier les refus pour provenance directe, en-tetes forges, identite absente ou ambigue, compte non administrateur et panne de verification, en conservant les tests `test_app.py` et `test_ha_auth.py`.
- [x] 1.4 Documenter les particularites ingress et le protocole de validation progressive dans le README de developpement ; verifier les commandes focalisees des tests backend et navigateur et distinguer explicitement flux simule et flux reel Supervisor.

## 2. Options de lancement et identifiants

- [x] 2.1 Ajouter la lecture JSON structuree des options de l'app avant le chargement de `create_app` en ingress, valider `ha_internal_url` et renseigner `VTHERM_HA_INTERNAL_URL` ; verifier defaut, TLS et port personnalise, JSON corrompu, adresse invalide, fichier absent selon contexte et absence de valeur brute dans les diagnostics.
- [x] 2.2 Conserver les identifiants MCP et fournisseur par utilisateur et l'usage de `SUPERVISOR_TOKEN` uniquement pour le chemin Core de verification des droits ; verifier `test_ingress_identity_does_not_supply_an_mcp_token`, jeton MCP absent, isolation et masquage des secrets dans les tests existants.
- [x] 2.3 Documenter la priorite des options ingress et de l'environnement, les risques HTTP interne et la separation des jetons ; verifier les cas de lancement documentes et les tests autonomes/OAuth sans Supervisor ni lecture des options HA OS.

## 3. Image Linux et stockage

- [x] 3.1 Ajouter un `Dockerfile` racine et `.dockerignore`, avec base Python 3.14 slim Debian fixe et installation du paquet depuis `pyproject.toml` ; verifier une construction Linux, les imports applicatifs et ADK et la presence des fichiers HTML/PNG dans le paquet installe, sans venv, caches ou donnees locales.
- [x] 3.2 Figer les dependances de release et conserver l'inventaire de l'image ; verifier leur coherence avec les contraintes du paquet et construire puis tester les images `linux/arm64` et `linux/amd64`, en consignant revision de base, architectures et echecs eventuels sans les annoncer compatibles.
- [x] 3.3 Lancer le processus existant avec un compte stable, un volume `/data` vide puis reutilise, et `SIGTERM` ; verifier port 8099, arret dans le delai prevu, reprise de la base, permissions `0700`/`0600` et refus sans suppression ni elargissement des droits lorsque le stockage est mal protege.
- [x] 3.4 Documenter les commandes de construction et de verification, les dependances figees, le compte d'execution et le volume ; verifier la procedure avec des identifiants factices et relever taille et consommation au demarrage, sans inclure de secrets dans l'image ou les journaux.

## 4. Metadonnees et documentation Home Assistant

- [x] 4.1 Ajouter les metadonnees dans `apps/vtherm_assistant/config.yaml` avec ingress 8099, acces administrateur, barre laterale, configuration, demarrage, API Core et stade experimental ; verifier un manifeste parse et valide ainsi que la coherence version paquet/image et l'absence de port hote, montage HA, acces Docker, materiel ou role administrateur Supervisor.
- [x] 4.2 Declarer seulement les architectures verifiees par 3.2, l'option `ha_internal_url`, la commande du processus et `init: true` ; verifier la coherence des valeurs du manifeste avec les tests de lancement de 2.1 et 3.3. Si un watchdog est ajoute, verifier qu'il utilise TCP et ne sollicite pas une route privee HTTP.
- [x] 4.3 Configurer `backup: cold` et documenter stockage, interruption de l'app, secrets presents dans SQLite et sauvegardes, restauration isolee et limites de retour de version ; verifier la configuration par un test du manifeste et fournir une procedure ne demandant jamais une restauration HA complete pour revenir sur l'app.
- [x] 4.4 Ajouter README d'app, DOCS, changelog, traductions francaises/anglaises et ressources de marque reutilisees ; verifier images valides, options expliquees, installation/sidebar, prerequisites MCP officiel et VTherm, suppression des donnees, desinstallation et distinction entre cibles HA 2026.10/VTherm 10.6.3 et versions reellement testees.

## 5. Generation et publication de la distribution

- [x] 5.1 Generer localement un catalogue HA propre avec `repository.yaml` et le seul dossier de l'app, dans une sortie ignoree ; verifier son contenu, son manifeste avec image preconstruite et l'absence d'OpenSpec, configurations parasites, sources applicatives dupliquees, secrets et artefacts de developpement.
- [x] 5.2 Ajouter la CI de tests, construction et preparation multiarchitecture, avec Buildx ou actions builder maintenues et contexte source racine ; verifier configuration du workflow et checks locaux, puis documenter les permissions de publication, les images immuables et l'ordre image avant catalogue sans effectuer de push implicite.
- [x] 5.3 Apres accord explicite sur la publication, executer le workflow, publier l'image GHCR publique versionnee puis le catalogue dans la branche de distribution dediee ; verifier un telechargement anonyme pour chaque architecture declaree, les tags et labels compatibles Supervisor, et la version du catalogue pointant vers l'image deja disponible.
- [x] 5.4 Documenter l'adresse du catalogue et la procedure de release et mise a jour apres publication ; verifier que le chargement Supervisor ne detecte aucune fausse app OpenSpec et que les liens d'installation ciblent la distribution propre, sans requalifier automatiquement experimental en stable.

## 6. Validation integree et preuves HA OS

- [x] 6.1 Executer la suite de regression existante, les tests ajoutes et la validation OpenSpec stricte ; verifier preservation du mode autonome, protections des mutations, isolation, refus des outils MCP d'ecriture et masquage des secrets, puis consigner les commandes et resultats sans les assimiler aux essais reels.
- [x] 6.2 Relever versions et architecture de l'instance principale en lecture seule, puis obtenir l'accord avant installation de l'app experimentale ; verifier l'installation, l'ouverture Web UI/sidebar et le controle administrateur via le vrai WebSocket Supervisor, sans mise a jour HA/VTherm ni changement de chauffage ou d'exposition d'entites automatique.
- [ ] 6.3 Verifier une lecture MCP connue autorisee et une conversation progressive sur le vrai ingress ; consigner fragments visibles avant la fin, donnees comparees aux etats HA, outils effectivement appeles et absence d'appel de commande. Signaler outils manquants et limites historiques sans les contourner.
- [ ] 6.4 Verifier reprise apres redemarrage de l'app et mise a jour compatible, configuration et isolation ; utiliser deux comptes administrateurs existants si disponibles et un compte non administrateur pour le refus, sans creation de compte implicite. Consigner les essais impossibles et conserver les criteres non prouves ouverts.
- [ ] 6.5 Verifier les erreurs fournisseur et MCP et la relance sans fuite de secrets ni sauvegarde d'une reponse incomplete ; utiliser des simulations controlees ou une configuration de test autorisee sans interrompre HA principal, et distinguer ces preuves des pannes reelles observees.
- [ ] 6.6 Apres accord pour chaque operation, verifier sauvegarde cold puis restauration limitees a l'app avec des donnees de test identifiables ; constater leur coherence, l'ecrasement limite a l'app et la preservation de HA/VTherm, puis consigner les limites si ces operations ne sont pas autorisees.

## Workflow follow-up

- Presenter les preuves et les criteres ouverts avant qualification ou archivage ; le stade experimental ne dispense pas de verifier les controles d'acces.
- Rapprocher, apres accord, les preuves de ce change des taches HA OS 8.1 et volets 8.3 a 8.5 de `add-vtherm-ai-assistant`, sans cloturer le deploiement Container ou les diagnostics historiques non valides.
- L'archivage et la synchronisation des specifications sont des operations ulterieures, non incluses dans la creation de ces artefacts.