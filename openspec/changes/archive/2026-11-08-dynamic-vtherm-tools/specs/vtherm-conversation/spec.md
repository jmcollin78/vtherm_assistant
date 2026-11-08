# Spec Delta

## MODIFIED Requirements

### Requirement: Lecture seule effective
Le système MUST exiger une confirmation explicite de l'utilisateur, distincte de la demande initiale, avant chaque appel d'outil VTherm qui peut modifier l'installation. La confirmation MUST porter sur l'action et ses paramètres exacts. L'assistant MUST NOT s'autoriser seul à effectuer une écriture. Les outils MCP Home Assistant hors VTherm MUST rester limités à des opérations de consultation autorisées.

#### Scenario: Demande de modification
- **WHEN** l'utilisateur demande de modifier une règle, une consigne ou un autre paramètre VTherm
- **THEN** l'assistant présente le VTherm cible, l'action et les paramètres exacts, puis attend une confirmation explicite avant tout appel d'écriture

#### Scenario: Confirmation de l'action précise
- **WHEN** l'utilisateur confirme explicitement l'action en attente et que sa cible et ses paramètres n'ont pas changé
- **THEN** le système exécute une seule fois l'appel d'écriture correspondant et rapporte son résultat réel

#### Scenario: Confirmation absente, refusée ou ambiguë
- **WHEN** l'utilisateur ne confirme pas, refuse, ou fournit une réponse qui ne confirme pas clairement l'action exacte
- **THEN** aucun outil d'écriture n'est appelé et l'installation reste inchangée par cet appel

#### Scenario: Paramètres modifiés après confirmation
- **WHEN** la cible ou un paramètre de l'appel change après l'obtention de la confirmation
- **THEN** la confirmation précédente n'est plus valide et le système demande une nouvelle confirmation avant d'exécuter l'appel modifié

#### Scenario: Tentative d'appel d'un outil de commande
- **WHEN** le modèle tente d'appeler un outil d'écriture VTherm sans confirmation valide associée à cet appel
- **THEN** le système bloque l'appel avant toute modification

#### Scenario: Outil d'écriture Home Assistant hors VTherm
- **WHEN** le modèle tente d'utiliser un outil MCP standard Home Assistant qui modifie l'installation
- **THEN** le système refuse l'appel, car seuls les outils de consultation retenus sont autorisés hors VTherm