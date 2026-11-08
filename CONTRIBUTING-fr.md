# Contribuer

Toute contribution, y compris documentaire, doit être cadrée par OpenSpec.
Une pull request n'est prête que lorsque toutes les tâches de son changement
sont réalisées, vérifiées et cochées, et que la validation OpenSpec stricte
réussit. Ne cochez jamais une tâche pour signaler une intention ou un test
simulé à la place d'une vérification demandée.

## Parcours OpenSpec

OpenSpec décrit les besoins et les changements dans
[`openspec/`](openspec/). Référence et installation :
[openspec.dev](https://openspec.dev/) et
[Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec).

Prompts de base disponibles dans les assistants configurés :

- `/opsx:explore` : clarifier un besoin ou comparer des options sans modifier
  le code ;
- `/opsx:propose <slug-et-besoin>` : créer proposal, spécifications, conception
  et tâches vérifiables ;
- `/opsx:apply` : implémenter les tâches du changement accepté et valider
  chaque étape ;
- `/opsx:archive` : archiver un changement terminé et synchroniser les
  spécifications après validation.

Pour chaque évolution, décrivez le comportement attendu, les exclusions, les
impacts sur Home Assistant, VTherm, MCP, fournisseurs et données, puis faites
valider le changement avant d'élargir le périmètre. Les tests réels et simulés
doivent être explicitement distingués. Une tâche non réalisable ou non vérifiée
reste ouverte et doit être résolue avant l'approbation de la PR ; ne réduisez
pas le périmètre en cours de route sans accord.

Avant de demander une revue :

1. Terminez toutes les cases de `tasks.md` avec les preuves demandées.
2. Exécutez `openspec validate --all --strict` et corrigez toute erreur.
3. Exécutez les tests concernés ; pour la suite complète, suivez les deux
  commandes du [guide de développement](docs/development-fr.md).
4. Mettez à jour le README, la documentation HA, les traductions ou le
   changelog lorsque le comportement utilisateur change.
5. Décrivez dans la PR le changement, les risques, les tests exécutés et les
   limites restantes. Toutes les tâches OpenSpec doivent être terminées pour
   que la PR soit validée.

## Conventions du dépôt

- Application Python dans `src/vtherm_assistant/`, interface dans
  `src/vtherm_assistant/frontend/`, tests dans `tests/` et application HA OS
  publique dans `apps/vtherm_assistant/`.
- Toute lecture ou écriture HA passe par le serveur MCP officiel. Les tests
  automatisés doivent employer des transports et données factices ; ne mettez
  jamais de jeton, clé API, identifiant, conversation privée ou sauvegarde dans
  une PR.
- Toute écriture VTherm doit afficher et valider explicitement sa cible et ses
  paramètres. N'ajoutez pas de commande HA générique, de contournement de la
  confirmation ou de surveillance autonome.
- Ne modifiez pas des appareils de chauffage réels pour valider un changement.
  Les essais intégrés d'écriture se font avec un VTherm simulé et une validation
  distincte de l'utilisateur.
- Conservez les protections de masquage, les permissions strictes du stockage
  et les frontières entre comptes. Ne journalisez pas de contenu brut d'outils,
  de messages ou de secrets.
- La publication d'image, la mise à jour du catalogue `ha-app`, la création
  d'une release et toute opération sur une instance HA réelle relèvent d'une
  autorisation explicite du mainteneur ; une PR ne les déclenche pas.

## Pull requests

Gardez chaque PR limitée au changement OpenSpec associé. Les tests ne doivent
pas dépendre d'un compte, d'un réseau domestique ou d'une clé réelle. Signalez
les validations impossibles au lieu de les présenter comme réussies. Les cases
OpenSpec laissées ouvertes, les tâches sans preuve ou un échec de validation
stricte empêchent la PR d'être considérée terminée.