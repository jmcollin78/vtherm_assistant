# Développement local

Ce guide décrit le lancement du backend et du proxy HTTPS de développement avec
une instance Home Assistant locale séparée. N'utilisez pas votre installation
de chauffage principale pour les essais d'écriture.

## Préparer l'environnement

Prérequis : Python 3.14, Git, Homebrew et une instance de test Home Assistant
accessible localement sur `http://127.0.0.1:8123`. L'instance HA doit démarrer
séparément de ce dépôt ; les tâches VS Code du projet ne démarrent que le proxy
Caddy et l'assistant.

Dans cette instance de test, installez Versatile Thermostat, créez un VTherm
avec des capteurs et un actionneur simulés, puis installez/configurez
l'intégration **Model Context Protocol** de Home Assistant. Publiez les outils
VTherm nécessaires via MCP et exposez le climate de test à Assist. Créez un
jeton longue durée avec un compte administrateur de test ; saisissez-le ensuite
dans l'interface, pas dans un fichier de configuration.

Depuis la racine du dépôt :

```sh
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

Sur Mac Apple Silicon, utilisez Python et ses dépendances en ARM64. Si le
terminal est sous Rosetta, ouvrez un shell natif avec `arch -arm64 /bin/bash`
avant de créer le venv.

## Démarrer l'application et le proxy

Dans VS Code, ouvrez la palette de commandes et choisissez
**Tasks: Run Task > VTherm: demarrer en local (HTTPS)**. Cette tâche démarre
en parallèle :

- le backend sur `127.0.0.1:8765`, accessible via `https://localhost:8443` ;
- le proxy Caddy et son relais vers l'interface Home Assistant,
  `https://localhost:8444` vers `http://127.0.0.1:8123`.

Au premier lancement, une fois le proxy en marche, exécutez aussi la tâche
**VTherm: approuver le certificat local**. macOS peut demander une autorisation
ou un mot de passe : saisissez-le directement dans le terminal. Cette tâche
ajoute l'autorité locale Caddy au trousseau ; elle n'est pas lancée
automatiquement. Ouvrez ensuite `https://localhost:8443`.

Si Home Assistant refuse les requêtes proxifiées, configurez ses réglages
**Trust X-Forwarded-For** et **Trusted proxies** avec l'adresse du proxy telle
qu'elle apparaît dans les journaux Home Assistant. Configurez l'URL navigateur
interne/externe appropriée pour `https://localhost:8444`. Ne désactivez pas la
vérification TLS et n'exposez pas ces ports à Internet.

Les tâches définissent un stockage autonome distinct :
`~/.local/share/vtherm-assistant-realtest`. Le mode local ne modifie pas les
options de l'app HA OS. Dans les paramètres de l'assistant, configurez le
fournisseur, le modèle, la clé éventuelle et le jeton MCP du compte de test.

Pour arrêter le proxy et le backend, utilisez **Tasks: Terminate Task** et
arrêtez les deux tâches enfants. Arrêtez l'instance HA séparément selon la
méthode utilisée pour la lancer.

## Vérifier le parcours

1. Connectez-vous avec un administrateur de test et vérifiez le modèle et la
   connexion MCP.
2. Démarrez une nouvelle conversation et comparez l'inventaire, l'état et le
   diagnostic d'un VTherm avec les informations visibles dans HA.
3. Vérifiez que les plugins, journaux et historiques ne sont rapportés que si
   les outils correspondants sont publiés par l'intégration.
4. Pour tester une écriture, utilisez uniquement un thermostat simulé : vérifiez
   la cible et tous les paramètres dans la demande de confirmation, refusez
   d'abord, puis faites un essai approuvé et vérifiez l'état final dans HA.
5. Redémarrez le backend et vérifiez la reprise de la dernière conversation.
   **Nouvelle conversation** doit remplacer cette session sans supprimer les
   secrets enregistrés.

Les données personnelles, identifiants, clés et jetons réels ne doivent jamais
être ajoutés aux tests ni au dépôt. Les suites automatisées utilisent des fournisseurs,
identités et serveurs MCP simulés.

## Tests

Installer les dépendances de développement puis exécuter les suites dans deux
processus pytest distincts :

```sh
python -m pytest -q --ignore=tests/test_frontend.py --ignore=tests/test_packaging.py
python -m pytest -q tests/test_frontend.py tests/test_packaging.py
```

Les tests navigateur utilisent Chromium sur ordinateur et mobile. Les tests de
conteneur nécessitent une image construite et `VTHERM_TEST_IMAGE` ; les
instructions sont dans le [guide de construction HA](ha-app-build-fr.md). Une
exécution sans cette variable ignore les tests Docker.

Les tests simulés ne prouvent pas la compatibilité avec un vrai fournisseur,
une version HA/VTherm, ni le streaming à travers un vrai ingress. Consignez
séparément les versions et résultats de tout essai intégré.