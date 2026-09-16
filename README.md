# Discord Bot Suite

Trois bots Discord en Python — **modération/sécurité**, **assistant LLM**, **gestion d'événements** — construits sur un socle commun, et livrés avec un **simulateur hors-ligne** qui rejoue des scénarios complets sans jeton Discord ni appel réseau.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m botsuite.sim all
```

Aucune clé, aucune connexion, aucun serveur Discord requis. Le simulateur démarre et déroule les quatre scénarios.

> L'environnement virtuel n'est pas de la politesse : sans lui, `pip install -e .` écrit dans le Python système et échoue avec `Permission denied` dès que l'installation n'est pas administrateur (cas classique sous Windows). Pour un simple coup d'œil sans rien installer, `PYTHONPATH=src python -m botsuite.sim all` suffit — le projet n'a aucune dépendance obligatoire pour le simulateur.

---

## Pourquoi ce projet est structuré comme ça

Le problème d'un bot Discord, c'est qu'il est difficile à tester : la logique vit à l'intérieur de gestionnaires d'événements qui ont besoin d'une connexion WebSocket vivante, d'un vrai serveur et de vrais utilisateurs pour se déclencher. On finit par « tester en prod », c'est-à-dire par se faire raider une fois pour découvrir que la règle ne marchait pas.

Ici, la logique métier ne connaît pas Discord.

```
                 ┌──────────────────────────────────────────┐
                 │  botsuite.security / llm / events        │
  entrée         │                                          │      sortie
  ─────────────▶ │  instantanés  ──▶  moteurs  ──▶  Décisions│ ─────────────▶
                 │  (dataclasses)                           │
                 └──────────────────────────────────────────┘
                        ▲                            │
                        │ conversion                 │ application
          ┌─────────────┴──────────────┐  ┌──────────┴───────────────┐
          │ adapters.discord_adapter   │  │ adapters.discord_adapter │
          │ (discord.py → snapshots)   │  │ (timeout, kick, ban…)    │
          └────────────────────────────┘  └──────────────────────────┘
                        ▲
          ┌─────────────┴──────────────┐
          │ botsuite.sim               │   ← monde scripté, horloge fausse
          │ (mêmes moteurs, sans API)  │
          └────────────────────────────┘
```

Les moteurs reçoivent des `MemberSnapshot` / `MessageSnapshot` et renvoient des `Decision`. Ils n'exécutent rien : bannir quelqu'un est le travail de l'adaptateur. Conséquences directes :

- **`import discord` n'apparaît que dans `adapters/`.** Le reste du projet s'importe et s'exécute sans la bibliothèque.
- **Le simulateur et le bot réel partagent le même code.** Un scénario n'est pas une maquette : il fait tourner le moteur de production.
- **Le temps est injecté** (`Clock`). Une fenêtre anti-raid de 30 secondes se teste en quelques microsecondes, et le résultat est reproductible au bit près — c'est ce qui permet aux scénarios de servir aussi de tests de non-régression.

---

## Le simulateur

```bash
python -m botsuite.sim list          # lister les scénarios
python -m botsuite.sim raid          # un seul
python -m botsuite.sim all           # tous
python -m botsuite.sim all --json    # résumé machine (utilisé par la CI)
```

| Scénario | Ce qu'il démontre |
|---|---|
| `raid` | 5 arrivées légitimes puis une vague de 30 comptes jetables → scoring de risque, verrouillage automatique, **zéro faux positif** sur les membres légitimes |
| `moderation` | Flood, cross-post, mention bomb, scam obfusqué, lien d'invitation → escalade graduée jusqu'au bannissement |
| `chat` | Contexte tronqué par budget de tokens, réponse longue découpée sous 2000 caractères sans casser les blocs de code, quota utilisateur, concurrence bornée |
| `tournament` | Inscriptions idempotentes, capacité, rappel unique, équipes équilibrées, **redémarrage du bot en cours de tournoi** |

Extrait de sortie (scénario `raid`) :

```
▸ Raid : 30 comptes créés cette semaine, sans avatar, noms générés
  free_nitro_01      risque 0.44  → ALLOW
  free_nitro_03      risque 0.72  → FLAG
  free_nitro_07      risque 0.92  → FLAG
✖ free_nitro_08      risque 0.90  → LOCKDOWN (déclenché au 8e compte de la vague)

▸ Bilan
  Comptes légitimes signalés : 0 / 5
  Comptes du raid signalés    : 29 / 30
  ✔ Verrouillage automatique après 8 arrivées de la vague
```

---

## Les trois bots

### 1. Sécurité et modération — `botsuite.security`

| Module | Rôle |
|---|---|
| `raid.py` | Détection de vague d'arrivées sur fenêtre glissante + score de risque par compte (âge, avatar, similarité des pseudonymes) |
| `spam.py` | Token bucket par auteur, détection de cross-post, mention bombing, liens d'invitation |
| `content.py` | Normalisation Unicode **avant** filtrage, puis règles regex |
| `sanctions.py` | Échelle de sanctions à points, avec décroissance exponentielle |
| `engine.py` | Assemblage → une `Decision` par événement, plus un journal d'audit |

**Le point non évident, c'est `content.py`.** Un filtre par mots-clés naïf se contourne en cinq secondes sur Discord. Ces huit écritures désignent la même arnaque :

```
free nitro · FREE NITRO · fr3e n1tro · f r e e   n i t r o
freeee nitrooo · fr​ee nit​ro (zero-width) · frее nitrо (cyrillique) · frée nitrö
```

`normalize()` les ramène toutes à `free nitro` — décomposition NFKD, suppression des diacritiques et des caractères de largeur nulle, table de confusables, dépliage leetspeak, écrasement des répétitions. `collapsed()` retire en plus les espaces, ce qui règle la variante lettre-par-lettre. Les règles restent alors lisibles, et [le test correspondant](tests/test_content.py) vérifie les huit variantes.

**Sur les faux positifs.** Un score de risque élevé ne suffit pas à déclencher un verrouillage : il faut *aussi* une vague. Un serveur populaire peut recevoir douze vraies inscriptions en douze secondes — [un test vérifie que ce cas ne verrouille pas](tests/test_raid.py). `SecurityEngine(dry_run=True)` permet de faire tourner une nouvelle règle en observation avant de lui donner le droit d'agir.

### 2. Assistant LLM — `botsuite.llm`

| Module | Rôle |
|---|---|
| `provider.py` | `Protocol` + `MockProvider` (déterministe, hors-ligne) + client compatible OpenAI |
| `context.py` | Fenêtre glissante sous budget de tokens, prompt système toujours conservé |
| `chunking.py` | Découpage sous la limite de 2000 caractères sans casser les blocs de code |
| `queue.py` | Quota par utilisateur + pool de workers borné |
| `service.py` | Orchestration, retourne une réponse déjà découpée |

Les trois contraintes qui font mal en production sont traitées explicitement :

- **Le contexte** ne peut pas contenir tout l'historique d'un salon. Les tours les plus anciens sautent en premier, le prompt système jamais.
- **Les 2000 caractères** de Discord : couper à l'aveugle casse les blocs de code en deux. Le splitter parcourt le texte comme une alternance de blocs fencés et de prose, et rouvre la fence à chaque morceau.
- **La concurrence** : sans file d'attente, dix utilisateurs simultanés produisent dix appels HTTP parallèles, le fournisseur répond 429, et tout le monde voit une erreur. Avec, ils attendent un peu.

Le provider par défaut est `mock` : le projet tourne entièrement sans clé d'API. Basculer sur un vrai modèle est une variable d'environnement.

### 3. Événements — `botsuite.events`

| Module | Rôle |
|---|---|
| `models.py` | Machine à états explicite (`draft → open → locked → running → finished`), sérialisable en JSON |
| `matchmaking.py` | Constitution d'équipes équilibrées, gloutonne et déterministe |
| `scoring.py` | Classement persistant par serveur |
| `service.py` | Persistance, planification, équipes, résultats |

**L'état vit dans le stockage, pas en mémoire.** Chaque mutation est écrite immédiatement, et le service ne garde aucun cache. Construire un second `EventService` sur le même stockage — ce qu'un redémarrage de processus est exactement — retrouve le monde identique. Le scénario `tournament` le fait au milieu d'un tournoi, et [un test l'assert](tests/test_events.py).

Côté Discord, les boutons d'inscription utilisent des *persistent views* (`timeout=None` + `custom_id` fixe), ré-enregistrées au chargement du cog : un message d'inscription publié la veille reste fonctionnel après un déploiement.

---

## Faire tourner le vrai bot

```bash
cp .env.example .env    # renseigner DISCORD_TOKEN
python -m botsuite.adapters.discord_adapter.bot
```

Ou avec Docker :

```bash
docker compose run --rm sim      # démo hors-ligne
docker compose up bot            # bot réel, nécessite .env
```

Intents privilégiés à activer dans le portail développeur Discord : `SERVER MEMBERS` et `MESSAGE CONTENT`.

Commandes disponibles : `/ask`, `/reset`, `/event-create`, `/leaderboard`, `/unlock`, `/forgive`.

---

## Tests

```bash
pytest -q        # 92 tests, < 1 s
ruff check .
```

La suite couvre chaque moteur isolément, plus les quatre scénarios de bout en bout. Aucun test n'a besoin du réseau, d'un jeton, ni de `discord.py` — la conversion des objets de la bibliothèque est testée contre des stubs *duck-typés*.

La CI GitHub Actions exécute lint + tests sur Python 3.11, 3.12 et 3.13, puis lance le simulateur comme smoke test.

---

## Ce que le projet ne fait pas

Autant l'écrire que le laisser découvrir :

- **Pas de sharding.** Au-delà de ~2500 serveurs, discord.py impose du sharding ; ce n'est pas implémenté.
- **Stockage clé/valeur, pas relationnel.** SQLite et un store mémoire sont fournis derrière un `Protocol`. PostgreSQL serait une classe de plus, mais elle n'est pas écrite.
- **Estimation de tokens approximative** (~4 caractères par token). Suffisant pour une fenêtre glissante, à remplacer par un vrai tokenizer si la comptabilité doit être exacte.
- **Table de confusables réduite** au sous-ensemble réellement croisé sur des serveurs communautaires, pas à la liste Unicode complète.
- **Pas de persistance des sanctions.** Les points d'infraction vivent en mémoire et repartent de zéro au redémarrage — délibéré pour l'instant (ils décroissent en une heure), mais c'est une limite réelle.

## Structure

```
src/botsuite/
├── clock.py            horloge injectable
├── models.py           instantanés + actions + verdicts
├── config.py           configuration par variables d'environnement
├── security/           raid · spam · contenu · sanctions · moteur
├── llm/                provider · contexte · découpage · file · service
├── events/             modèles · matchmaking · scoring · service
├── storage/            protocole + mémoire + sqlite
├── adapters/
│   └── discord_adapter/   le seul endroit qui importe discord.py
└── sim/                monde scripté + 4 scénarios + CLI
tests/                  88 tests
```

## Licence

MIT — voir [LICENSE](LICENSE).
