# Proposal

## Why

L'assistant fonctionne en mode local, mais ne dispose pas encore d'un paquet installable dans Home Assistant OS. Le transformer en app avec ingress permettra de l'ouvrir dans Home Assistant avec la session HA existante, sans adresse, certificat ni port public propres a l'assistant.

## What Changes

- Construire une image Linux de l'assistant existant avec Python 3.14 et ses ressources frontend, en visant `aarch64` et `amd64` et en ne declarant que les architectures verifiees.
- Ajouter les metadonnees d'une app HA OS experimentale : ingress, acces administrateur, barre laterale optionnelle, demarrage, configuration et stockage persistant.
- Adapter et tester les ressources et les parcours de l'interface sous le prefixe ingress, notamment le logo actuellement charge par une URL absolue.
- Configurer l'adresse interne HA depuis les options de l'app sans modifier l'authentification MCP par jeton utilisateur ni la configuration individuelle des fournisseurs.
- Preparer une distribution installable avec image preconstruite, documentation, icone, changelog et procedure de mise a jour. La publication et les operations sur HA constituent des jalons distincts soumis a accord.
- Verifier l'integration avec le Supervisor, la lecture seule, les refus d'acces, le streaming, la persistance et les sauvegardes de l'app, en distinguant tests simules et essais reels.

Le packaging HA Container, les nouveaux outils d'historique, la simplification de l'authentification MCP par le jeton Supervisor et la migration automatique des donnees locales sont exclus. Le mode autonome actuel est conserve, sans nouveau paquet de deploiement. Aucun changement de chauffage, de Recorder ou de configuration VTherm n'est requis.

## Capabilities

### New Capabilities

- `ha-app-deployment`: installation, configuration, acces ingress, cycle de vie et distribution de l'assistant comme app Home Assistant OS.

### Modified Capabilities

Aucune. Les exigences de conversation, de configuration des modeles et de lecture seule du change `add-vtherm-ai-assistant` restent des contraintes d'integration ; aucune specification principale n'est actuellement publiee dans `openspec/specs`.

## Impact

- Reutilisation de `src/vtherm_assistant/__main__.py`, de `create_app`, d'`AccessMiddleware`, de `verify_ingress_admin` et du stockage SQLite existants ; adaptations limitees au lancement et aux parcours ingress.
- Correction de ressources frontend et extension des tests backend et navigateur existants ; ajout du conteneur, des metadonnees HA et des controles de packaging et de distribution.
- Acces a l'API Core via le Supervisor pour verifier les administrateurs, sans privileges materiels ni montage de la configuration HA. Le jeton MCP reste distinct de l'identite ingress.
- Les appels aux fournisseurs distants et les donnees susceptibles de leur etre transmises ne changent pas. Les secrets persistent dans le volume prive de l'app et doivent etre proteges aussi dans ses sauvegardes.
- Les cibles HA 2026.10 et VTherm 10.6.3 du design existant restent a verifier sur les versions effectivement utilisees. Les essais reels ne disposent actuellement que de l'instance HA OS principale de l'utilisateur : installation, sauvegarde et restauration necessitent son accord specifique.
- Ce change detaille le lot HA OS de la section 8 de `add-vtherm-ai-assistant` : 8.1 et volets OS de 8.3 a 8.5. Il ne clot pas ces taches automatiquement, ne supprime pas 8.2 et ne depend pas de l'achevement des nouvelles fonctions historiques ou de l'archivage du change initial.