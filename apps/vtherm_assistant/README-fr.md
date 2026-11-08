# Assistant VTherm

![VTherm](logo.png)

Assistant conversationnel pour diagnostiquer les thermostats Versatile
Thermostat depuis Home Assistant OS. Il découvre tous les outils VTherm publiés
par le serveur MCP dont le schéma est accepté et peut analyser les états,
l'historique et les autres diagnostics qu'ils fournissent.

Il peut aussi rechercher dans la documentation en ligne officielle de VTherm,
[versatile-thermostat.org](https://www.versatile-thermostat.org/), en français,
anglais ou allemand. La recherche retourne des extraits ciblés, pas une copie
exhaustive du site.

Les actions VTherm publiées (par exemple mode, consigne, preset ou marche/arrêt)
exigent chacune une confirmation explicite de la cible et de tous les
paramètres dans l'interface. Vérifiez toujours dans Home Assistant ce qui a
réellement changé. Les possibilités dépendent de VTherm, des outils MCP publiés
et acceptés, ainsi que de l'entité choisie ; les commandes générales d'écriture
Home Assistant ne sont pas accessibles.

**Ne saisissez aucun secret dans les conversations.** Les messages et les
résultats utilisés pour répondre sont transmis au fournisseur de modèle
configuré. Les clés API et le jeton Home Assistant doivent uniquement être
enregistrés dans leurs champs dédiés.

Catalogue de l'app :
`https://github.com/jmcollin78/vtherm_assistant#ha-app`

Consultez [DOCS](DOCS-fr.md) pour l'installation, la configuration MCP, le jeton
longue durée, le choix du modèle, la reprise de conversation, les sauvegardes et
les restaurations.