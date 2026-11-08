# Spec Delta

## ADDED Requirements

### Requirement: Historique des états du VTherm et de ses dépendances
Le système MUST consulter, lorsque l'outil de lecture est disponible, l'historique du VTherm sélectionné et des seules entités qui lui sont liées. Il MUST préciser la période et les limites effectives des données retournées, sans reconstruire les valeurs absentes de l'historique.

#### Scenario: Historique disponible
- **WHEN** l'utilisateur demande l'évolution d'un VTherm et que son historique ou celui d'une entité liée est accessible
- **THEN** l'assistant rapporte les états observés avec leurs horodatages et identifie les entités consultées

#### Scenario: Historique incomplet ou indisponible
- **WHEN** une entité liée est exclue de Recorder, que la période demandée dépasse les données conservées ou que l'accès est refusé
- **THEN** l'assistant indique la période ou les données manquantes et limite ses conclusions aux observations disponibles

### Requirement: Consultation des plugins liés à un VTherm
Le système MUST pouvoir consulter les plugins installés et leur configuration pour un seul VTherm par appel d'outil. L'assistant MUST distinguer la configuration effectivement retournée des informations inconnues ou inaccessibles.

#### Scenario: Plugins et configuration accessibles
- **WHEN** l'outil VTherm retourne les plugins configurés pour le thermostat sélectionné
- **THEN** l'assistant peut utiliser ces informations pour expliquer son comportement sans supposer de paramètres non retournés

#### Scenario: Plugin ou configuration inaccessible
- **WHEN** l'outil est absent, échoue ou ne retourne pas la configuration d'un plugin pertinent
- **THEN** l'assistant signale cette limite et ne prétend pas connaître le plugin ou sa règle de configuration

### Requirement: Consultation des journaux techniques d'un VTherm
Le système MUST pouvoir consulter les journaux techniques bruts d'un seul VTherm par appel d'outil et MUST signaler leur période et toute limite ou troncature connue.

#### Scenario: Journaux du thermostat sélectionné
- **WHEN** l'utilisateur demande l'analyse d'un incident et que les journaux du VTherm sélectionné sont accessibles
- **THEN** l'assistant utilise uniquement les journaux associés à ce VTherm et distingue les messages observés de ses hypothèses

#### Scenario: Journaux absents ou limités
- **WHEN** aucun journal pertinent n'est retourné, que la lecture échoue ou que le résultat est tronqué
- **THEN** l'assistant indique cette limite et ne traite pas l'absence de lignes retournées comme la preuve qu'aucun incident n'a eu lieu

### Requirement: Sources de diagnostic limitées au VTherm
Les lectures ajoutées pour ce diagnostic MUST rester limitées au VTherm sélectionné et aux entités explicitement liées par les données VTherm. Le système MUST NOT effectuer de recherche générale dans Home Assistant ni consulter des journaux ou entités sans lien avec ce VTherm.

#### Scenario: Entité non liée au VTherm
- **WHEN** une entité Home Assistant n'est pas identifiée comme liée au VTherm sélectionné
- **THEN** l'assistant ne consulte pas son état ou son historique au titre de ce diagnostic

### Requirement: Protection des nouvelles sources de diagnostic
Le système MUST masquer les secrets avant de transmettre les résultats des outils au fournisseur de modèle et MUST traiter les journaux et configurations retournés comme des données non fiables, jamais comme des instructions.

#### Scenario: Secret ou instruction dans une source
- **WHEN** un journal ou une configuration contient un secret ou du texte ressemblant à une instruction
- **THEN** le secret n'est pas transmis au fournisseur et le texte est interprété uniquement comme une donnée source