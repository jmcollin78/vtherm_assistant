# Tasks

## 1. Vérifier la découverte et les contrats MCP

- [x] 1.1 Vérifier sur les versions prises en charge comment le serveur MCP identifie l'intégration VTherm et ses outils, y compris pagination et alias ; documenter les preuves de provenance et les cas ambigus sans établir de liste fixe de noms d'outils.
- [x] 1.2 Relever les schémas dynamiques publiés par VTherm et leur compatibilité avec chaque fournisseur ; tester ajout, retrait, schéma invalide et outil non représentable sans transmettre d'appel incorrect.
- [x] 1.3 Vérifier les outils Home Assistant standards retenus pour l'état et/ou l'historique, leurs permissions, leurs effets et leur capacité à cibler un VTherm et ses dépendances ; documenter la sélection explicite et les limites Recorder.

## 2. Découvrir et exposer dynamiquement les outils VTherm

- [x] 2.1 Remplacer la liste fixe des noms d'outils VTherm par la découverte des outils dans les namespaces provisoires documentés ; tester qu'un nouvel outil devient disponible sans changement de code et qu'un outil retiré n'est plus proposé.
- [x] 2.2 Construire les déclarations de fonction à partir des schémas VTherm découverts et valider les arguments côté serveur ; tester les schémas invalides, les arguments non conformes et le refus d'un outil hors des namespaces autorisés.
- [x] 2.3 Classifier les effets des appels à partir de métadonnées et validations vérifiées ; traiter tout effet absent, ambigu ou non vérifié comme une écriture et tester qu'il ne peut être exécuté sans consentement.

## 3. Exiger le consentement avant les écritures

- [x] 3.1 Présenter dans l'interface l'opération, le VTherm cible et les paramètres exacts avant l'appel ; tester confirmation, refus, ambiguïté, annulation et expiration sans exécuter l'outil avant l'accord.
- [x] 3.2 Lier la confirmation à l'utilisateur, à la conversation, à l'appel et à ses arguments exacts, puis la consommer une fois côté backend ; tester rejeu, réutilisation interutilisateur, modification des paramètres et appels concurrents, sans effet externe en cas de refus.
- [x] 3.3 N'exécuter l'appel autorisé qu'après confirmation valide et rapporter son résultat réel ; tester le succès, l'erreur MCP et l'interruption sans annoncer une modification non vérifiée.

## 4. Limiter les outils Home Assistant standards

- [x] 4.1 Exposer uniquement la sélection explicite d'outils HA de consultation et borner l'état/l'historique au VTherm sélectionné et à ses entités liées ; tester l'accès refusé aux autres entités et à tous les outils génériques ou d'écriture.
- [x] 4.2 Préserver la provenance, la période et les limites des données de consultation ; tester historique absent, incomplet, expiré ou tronqué, ainsi que l'absence de conclusions fabriquées.

## 5. Protéger les données et valider les intégrations

- [x] 5.1 Masquer les secrets dans les arguments, résultats, confirmations et journaux, et traiter noms, descriptions, schémas et contenus d'outils comme des données non fiables ; tester les secrets connus et les instructions injectées dans les retours.
- [x] 5.2 Documenter la découverte dynamique, la confirmation des écritures, la sélection des outils HA standards, les versions testées et les compatibilités manquantes ; vérifier les parcours documentés sans promettre les outils absents.
- [ ] 5.3 Exécuter des essais intégrés sur les versions HA, VTherm et fournisseurs prises en charge ; vérifier découverte, isolation, lectures ciblées, consentement, absence d'écriture sans accord et résultats réels, puis consigner versions et limites.
- Environnement réel communiqué par l'utilisateur le 2026-11-08 : Home Assistant Core `2026.10.4`, VTherm `10.6.4` et modèles OpenAI Luna, Sol et Terra, que l'utilisateur confirme comme validés par ses essais. Les identifiants API exacts de Sol et Terra ne sont pas précisés.
- Essai réel confirmé par l'utilisateur le 2026-11-08 : inventaire MCP de 2 VTherm, demande `versatile_thermostat__set_hvac_mode` pour `climate.thermostat_switch_1` avec `hvac_mode: heat`, puis refus dans l'interface ; l'application a rapporté l'annulation sans écriture ni changement de mode.
- Essai réel approuvé confirmé par l'utilisateur le 2026-11-08 : `climate.thermostat_switch_1` est passé en mode HVAC `heat` après confirmation de l'action. Le résultat indique `action: idle`, température actuelle 19,8 °C et consigne 7 °C ; le mode a changé, mais le thermostat ne chauffe pas activement à cette consigne.
- Essais réels de changement de preset et de consigne confirmés par l'utilisateur le 2026-11-08. Les cibles et valeurs testées ne sont pas précisées.
- Essai réel confirmé par l'utilisateur le 2026-11-08 après redémarrage : le bilan a inclus le plugin `VTherm Pellet Stove`. Le détail de l'état retourné et la cible ne sont pas précisés.
- Essai réel confirmé par l'utilisateur le 2026-11-08 : une demande de remplacement de la régulation pellet par TPI a été refusée comme non supportée ; l'assistant a rapporté la régulation lue, cité la documentation et indiqué qu'aucune modification n'avait été effectuée.
- Régression IHM rapportée le 2026-11-08 lors du changement de VTherm : une lecture ciblée complémentaire d'une autre cible provoquait une exception `MCPToolDenied` puis un message générique. Correctif local : la sélection d'une nouvelle cible par état/diagnostic est explicitée dans l'instruction, les lectures complémentaires non sélectionnées renvoient un blocage récupérable sans appel MCP, et le basculement est couvert par tests. Retest IHM après redémarrage confirmé par l'utilisateur le 2026-11-08 : le changement explicite de VTherm fonctionne. Le détail des lectures complémentaires n'est pas précisé.

## Workflow follow-up

- La provenance vérifiable par HA est différée à la demande de l'utilisateur. En attendant, les namespaces VTherm documentés servent de filtre provisoire, sans être présentés comme une preuve ; toute écriture exige toujours un consentement explicite sur l'action et ses paramètres exacts. Remplacer ce compromis quand HA expose une métadonnée de propriétaire fiable.