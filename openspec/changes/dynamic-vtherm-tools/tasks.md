# Tasks

## 1. Vérifier la découverte et les contrats MCP

- [ ] 1.1 Vérifier sur les versions prises en charge comment le serveur MCP identifie l'intégration VTherm et ses outils, y compris pagination et alias ; documenter les preuves de provenance et les cas ambigus sans établir de liste fixe de noms d'outils.
- [ ] 1.2 Relever les schémas dynamiques publiés par VTherm et leur compatibilité avec chaque fournisseur ; tester ajout, retrait, schéma invalide et outil non représentable sans transmettre d'appel incorrect.
- [ ] 1.3 Vérifier les outils Home Assistant standards retenus pour l'état et/ou l'historique, leurs permissions, leurs effets et leur capacité à cibler un VTherm et ses dépendances ; documenter la sélection explicite et les limites Recorder.

## 2. Découvrir et exposer dynamiquement les outils VTherm

- [ ] 2.1 Remplacer la liste fixe des noms d'outils VTherm par la découverte des outils dont l'origine VTherm est vérifiée ; tester qu'un nouvel outil devient disponible sans changement de code et qu'un outil retiré n'est plus proposé.
- [ ] 2.2 Construire les déclarations de fonction à partir des schémas VTherm découverts et valider les arguments côté serveur ; tester les schémas invalides, les arguments non conformes et le refus d'un outil dont l'origine ne peut pas être établie.
- [ ] 2.3 Classifier les effets des appels à partir de métadonnées et validations vérifiées ; traiter tout effet absent, ambigu ou non vérifié comme une écriture et tester qu'il ne peut être exécuté sans consentement.

## 3. Exiger le consentement avant les écritures

- [ ] 3.1 Présenter dans l'interface l'opération, le VTherm cible et les paramètres exacts avant l'appel ; tester confirmation, refus, ambiguïté, annulation et expiration sans exécuter l'outil avant l'accord.
- [ ] 3.2 Lier la confirmation à l'utilisateur, à la conversation, à l'appel et à ses arguments exacts, puis la consommer une fois côté backend ; tester rejeu, réutilisation interutilisateur, modification des paramètres et appels concurrents, sans effet externe en cas de refus.
- [ ] 3.3 N'exécuter l'appel autorisé qu'après confirmation valide et rapporter son résultat réel ; tester le succès, l'erreur MCP et l'interruption sans annoncer une modification non vérifiée.

## 4. Limiter les outils Home Assistant standards

- [ ] 4.1 Exposer uniquement la sélection explicite d'outils HA de consultation et borner l'état/l'historique au VTherm sélectionné et à ses entités liées ; tester l'accès refusé aux autres entités et à tous les outils génériques ou d'écriture.
- [ ] 4.2 Préserver la provenance, la période et les limites des données de consultation ; tester historique absent, incomplet, expiré ou tronqué, ainsi que l'absence de conclusions fabriquées.

## 5. Protéger les données et valider les intégrations

- [ ] 5.1 Masquer les secrets dans les arguments, résultats, confirmations et journaux, et traiter noms, descriptions, schémas et contenus d'outils comme des données non fiables ; tester les secrets connus et les instructions injectées dans les retours.
- [ ] 5.2 Documenter la découverte dynamique, la confirmation des écritures, la sélection des outils HA standards, les versions testées et les compatibilités manquantes ; vérifier les parcours documentés sans promettre les outils absents.
- [ ] 5.3 Exécuter des essais intégrés sur les versions HA, VTherm et fournisseurs prises en charge ; vérifier découverte, isolation, lectures ciblées, consentement, absence d'écriture sans accord et résultats réels, puis consigner versions et limites.

## Workflow follow-up

- Réconcilier la politique globale de lecture seule dans `openspec/config.yaml` avant d'appliquer ce changement ; cette modification reste hors du périmètre autorisé pour les artefacts de ce changement.