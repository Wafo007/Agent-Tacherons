# W4FO — Backend

Backend de l'assistant IA personnel **W4FO**, construit en **Clean Architecture** (Python / FastAPI / PostgreSQL / LangGraph / Mistral AI).

> Ce dépôt correspond à la V2 complète de la roadmap définie dans le document d'architecture (`W4FO_Architecture.md`) : squelette Clean Architecture, authentification JWT, module Tâches, intégration Mistral AI, graphe d'agents LangGraph (routage conversation générale / tâches / agenda, tool calling, mémoire contextuelle chargée et écrite automatiquement à chaque tour, mécanisme de confirmation des actions sensibles), conversation vocale temps réel (WebSocket STT → LangGraph → TTS), module Agenda avec Google Calendar (OAuth, CRUD, détection de conflits), module Mémoire long terme (pgvector, recherche sémantique), et réveil intelligent (scheduler proactif **avec gestion des fuseaux horaires par utilisateur**, briefing matinal, notifications, paramètres utilisateur). Le backend V2 est donc fonctionnellement complet ; la V3 (RAG documentaire, Gmail, consolidation avancée, boucle multi-outils) reste à implémenter — voir "Prochaines étapes" ci-dessous. Le développement du frontend Flutter peut démarrer sur cette base.

## Sommaire

- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Lancement](#lancement)
- [Migrations de base de données](#migrations-de-base-de-données)
- [Tests](#tests)
- [Structure du projet](#structure-du-projet)
- [Endpoints disponibles](#endpoints-disponibles)
- [Prochaines étapes](#prochaines-étapes)

## Architecture

Le projet suit strictement la **Clean Architecture** avec 4 couches, où les dépendances pointent toujours vers le domaine :

```
presentation  →  application  →  domain  ←  infrastructure
```

- **`domain/`** : entités métier (dataclasses pures), value objects, interfaces (ports). Aucune dépendance externe — ni FastAPI, ni SQLAlchemy, ni Mistral.
- **`application/`** : use cases qui orchestrent le domaine (ex: `CreateTaskUseCase`), DTOs de transfert.
- **`infrastructure/`** : implémentations concrètes des interfaces du domaine (adapters) — SQLAlchemy pour la persistance, Mistral SDK pour le LLM, LangGraph pour les agents.
- **`presentation/`** : couche HTTP — routers FastAPI, schémas Pydantic, WebSocket.
- **`core/`** : configuration, sécurité JWT, injection de dépendances, exceptions.

Le fichier `core/dependencies.py` est le seul endroit où le domaine est "câblé" à une implémentation concrète (`UserRepository` → `SQLAlchemyUserRepository`). Cela permet de changer de base de données ou de fournisseur LLM sans toucher à la logique métier.

## Prérequis

- Python 3.12+
- Une base de données PostgreSQL 15+ avec l'extension `pgvector` activée — deux options :
  - **Docker & Docker Compose** (voir `docker-compose.yml`, active pgvector automatiquement)
  - **[Supabase](https://supabase.com)** (recommandé si tu ne veux pas installer PostgreSQL/pgvector toi-même — voir section dédiée ci-dessous)
- `ffmpeg` installé sur la machine (requis par `faster-whisper` pour le décodage audio)
- Une clé API Mistral AI

## Utiliser Supabase comme base de données (sans Docker ni installation locale de PostgreSQL)

Supabase fournit un PostgreSQL managé avec `pgvector` déjà disponible — plus simple que de l'installer/compiler soi-même en local.

1. Crée un compte et un projet sur [supabase.com](https://supabase.com) (le plan gratuit suffit largement pour le développement).
2. Dans le dashboard du projet, ouvre l'**Éditeur SQL** et exécute :
   ```sql
   create extension if not exists vector;
   ```
3. Va dans **Project Settings → Database → Connection string**, onglet **URI**, et copie la chaîne de **connexion directe** (port `5432`) — **pas** le pooler (port `6543`, voir avertissement ci-dessous).
4. Colle-la dans `.env` sous `DATABASE_URL`, en remplaçant le préfixe `postgresql://` par `postgresql+asyncpg://` :
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:TON_MOT_DE_PASSE@db.TON_PROJET.supabase.co:5432/postgres
   ```
5. Applique les migrations comme d'habitude : `alembic upgrade head`.

> ⚠️ **Piège PgBouncer** : si tu utilises le connection pooler Supabase (port `6543`, mode "Transaction"), les requêtes préparées d'asyncpg ne fonctionnent pas correctement avec ce mode. Le projet désactive déjà leur cache par défaut (`statement_cache_size=0` dans `database.py` et `alembic/env.py`) pour rester compatible dans les deux cas — mais privilégie la connexion directe (port `5432`) en développement, le pooler étant surtout utile en production à forte concurrence.
>
> Supabase exige aussi une connexion chiffrée (SSL) même en connexion directe — déjà géré automatiquement par le projet (`connect_args={"ssl": "require"}`), aucune action nécessaire de ta part.

## Installation

```bash
# 1. Cloner / se placer dans le dossier du projet
cd w4fo-backend

# 2. Créer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate sous Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Copier et configurer les variables d'environnement
cp .env.example .env
# Éditer .env : renseigner DATABASE_URL (voir section Supabase ci-dessus, ou Docker),
# MISTRAL_API_KEY, JWT_SECRET_KEY (générer une chaîne aléatoire longue), etc.
```

## Lancement

### Option A — Avec Docker Compose (recommandé)

```bash
docker compose up --build
```

Cela démarre PostgreSQL (avec l'extension `pgvector` activée automatiquement) et l'API FastAPI en rechargement automatique.

### Option B — En local, PostgreSQL via Docker uniquement

```bash
# Démarrer uniquement PostgreSQL via Docker
docker compose up postgres -d

# Appliquer les migrations
alembic upgrade head

# Lancer l'API
uvicorn src.main:app --reload
```

### Option C — Sans Docker du tout (avec Supabase)

```bash
# DATABASE_URL dans .env pointe déjà vers Supabase (voir section dédiée ci-dessus)

# Appliquer les migrations
alembic upgrade head

# Lancer l'API — --host 0.0.0.0 nécessaire pour être accessible depuis un téléphone
# physique sur le même réseau Wi-Fi (test de l'app Flutter sur un vrai appareil)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

L'API est alors disponible sur `http://localhost:8000`, avec la documentation interactive Swagger sur `http://localhost:8000/docs`.

## Migrations de base de données

Le projet utilise **Alembic** pour versionner le schéma PostgreSQL.

```bash
# Générer une nouvelle migration après modification des modèles SQLAlchemy
alembic revision --autogenerate -m "description du changement"

# Appliquer les migrations
alembic upgrade head

# Revenir en arrière d'une migration
alembic downgrade -1
```

> ⚠️ Toujours relire une migration auto-générée avant de l'appliquer : `--autogenerate` ne détecte pas tout (renommages de colonnes, certains types).

## Tests

```bash
# Tests unitaires (domaine pur, rapides, sans base de données)
pytest tests/unit -v

# Tous les tests (nécessite PostgreSQL démarré pour les tests d'intégration)
pytest -v

# Avec couverture de code
pytest --cov=src --cov-report=term-missing
```

Les tests unitaires du domaine (`tests/unit/test_task_entity.py`) illustrent l'intérêt de la Clean Architecture : ils valident les règles métier (ex: impossible de reporter une tâche terminée) sans dépendre de FastAPI ni de la base de données.

## Structure du projet

```
w4fo-backend/
├── alembic/                    # Migrations de base de données
├── src/
│   ├── domain/                 # Cœur métier — zéro dépendance externe
│   │   ├── entities/           # User, Task...
│   │   ├── value_objects/      # Priority, TaskStatus, AutonomyLevel
│   │   ├── repositories/       # Interfaces (ports)
│   │   └── services/           # Interfaces (ports) — LLMProvider...
│   ├── application/            # Use cases + DTOs
│   │   ├── use_cases/
│   │   │   ├── auth/
│   │   │   └── manage_tasks/
│   │   └── dto/
│   ├── infrastructure/         # Implémentations concrètes (adapters)
│   │   ├── persistence/        # SQLAlchemy : modèles, repositories, session DB
│   │   ├── llm/                # Intégration Mistral AI (à venir)
│   │   ├── voice/              # STT/TTS (à venir)
│   │   ├── agents/             # Orchestration LangGraph (à venir)
│   │   └── scheduler/          # Tâches proactives (à venir)
│   ├── presentation/           # API HTTP
│   │   ├── api/v1/             # Routers REST
│   │   ├── api/websocket/      # WebSocket voix (à venir)
│   │   └── schemas/            # Schémas Pydantic
│   ├── core/                   # Config, sécurité JWT, DI, exceptions
│   └── main.py                 # Point d'entrée FastAPI
├── tests/
│   ├── unit/                   # Tests du domaine pur
│   ├── integration/            # Tests avec base de données
│   └── e2e/                    # Tests bout en bout de l'API
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Endpoints disponibles

### Authentification (`/api/v1/auth`)

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Inscription d'un nouvel utilisateur |
| POST | `/api/v1/auth/login` | Connexion, retourne un access token + refresh token |

### Tâches (`/api/v1/tasks`) — nécessite un token Bearer

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/tasks` | Créer une tâche |
| GET | `/api/v1/tasks` | Lister les tâches de l'utilisateur (filtres : `status_filter`, `category`) |
| PATCH | `/api/v1/tasks/{task_id}` | Mettre à jour une tâche |
| DELETE | `/api/v1/tasks/{task_id}` | Supprimer une tâche |

### Conversation (`/api/v1/conversation`) — nécessite un token Bearer

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/conversation/message` | Envoie un message texte à l'orchestrateur d'agents (router → chat/task agent) |

### Santé

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | Vérification de disponibilité du service |

## Orchestrateur d'agents (LangGraph)

Le graphe (`src/infrastructure/agents/graph_builder.py`) implémente le flux suivant :

```
router (classification LLM) ──▶ chat_agent ──▶ END
                             └─▶ task_agent ──▶ (outil sensible ?) ──▶ END (demande de confirmation)
                                             └─▶ execute_tool ──▶ END
```

- **`router_node`** : demande au LLM de classifier l'intention (`task` ou `chat`).
- **`chat_agent_node`** : répond directement pour les échanges généraux.
- **`task_agent_node`** : utilise le function calling Mistral avec les outils définis dans `agents/tools/task_tools.py` (`task_create`, `task_list`, `task_update`, `task_delete`).
- **Classification de sensibilité** : `task_delete` est marqué comme action sensible (`SENSITIVE_TOOLS`). Si détecté, le graphe s'arrête et renvoie `requires_confirmation=True` au lieu d'exécuter l'action — conformément au §6.4 du document d'architecture.
- **`execute_pending_tool_node`** : exécute l'outil validé et reformule le résultat en langage naturel.

Tester rapidement (une fois authentifié) :

```bash
curl -X POST http://localhost:8000/api/v1/conversation/message \
  -H "Authorization: Bearer <votre_access_token>" \
  -H "Content-Type: application/json" \
  -d '{"content": "Crée-moi une tâche urgente : préparer la présentation client pour demain"}'
```

## Conversation vocale temps réel (WebSocket)

Endpoint : `ws://localhost:8000/ws/v1/voice?token=<access_token>&voice_id=default`

Implémente la séquence du §10.1 du document d'architecture : le client envoie des chunks audio bruts (frames binaires), signale la fin de parole via un événement JSON, puis reçoit la transcription, la réponse texte, et l'audio de synthèse en streaming.

**Choix techniques par défaut (V1)**, volontairement laissés ouverts dans le document d'architecture (§10.2) :
- **STT** : [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — modèle Whisper exécuté localement, sans clé API cloud. Modèle `base` par défaut (réglable dans `FasterWhisperSTTProvider`).
- **TTS** : [edge-tts](https://github.com/rany2/edge-tts) — voix Microsoft Edge, gratuites, plusieurs voix françaises (`fr-FR-DeniseNeural`, `fr-FR-HenriNeural`).

Ces deux choix sont entièrement swappables : ils implémentent respectivement les interfaces `STTProvider` et `TTSProvider` du domaine (`src/domain/services/`). Passer à un fournisseur cloud (Azure Speech, ElevenLabs...) ne nécessite que d'écrire une nouvelle classe et de mettre à jour `get_stt_provider`/`get_tts_provider` dans `core/dependencies.py`.

**Protocole du canal** (messages JSON envoyés par le serveur) :

| Événement | Description |
|---|---|
| `transcript` | Texte transcrit du segment de parole de l'utilisateur |
| `agent_thinking` | Signale que l'orchestrateur traite la demande (permet d'afficher un indicateur côté client) |
| `response_text` | Texte de la réponse de l'assistant |
| `requires_confirmation` | Une action sensible a été détectée ; contient le `tool_call` en attente |
| `end_of_turn` | Fin du tour ; le client peut réactiver le micro |

Le client envoie `{"event": "end_of_speech"}` pour signaler la fin de son segment de parole, ou `{"event": "interrupt"}` pour un barge-in (couper la réponse en cours).

**Limitation V1 assumée** : la transcription attend la fin complète du segment audio (pas de transcription incrémentale par VAD), et le TTS démarre une fois la réponse texte complète générée (pas encore de découpage phrase par phrase). Ces optimisations de latence, décrites au §10.2, sont prévues pour V2.

## Module Agenda (Google Calendar)

### Configuration OAuth requise

1. Créer un projet dans la [Google Cloud Console](https://console.cloud.google.com/), activer l'API Google Calendar.
2. Créer des identifiants OAuth 2.0 (type "Application Web").
3. Renseigner dans `.env` : `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` (URI de redirection configurée côté Google Cloud, généralement gérée côté client Flutter via le SDK Google Sign-In).

### Flow de connexion

Le flow OAuth (redirection, écran de consentement Google) est piloté côté client Flutter. Le backend n'intervient qu'à la toute fin :

```bash
# Une fois le code d'autorisation obtenu côté client
curl -X POST http://localhost:8000/api/v1/calendar/connect/callback \
  -H "Authorization: Bearer <votre_access_token>" \
  -H "Content-Type: application/json" \
  -d '{"authorization_code": "<code_recu_de_google>"}'
```

> ⚠️ Google ne renvoie le `refresh_token` que lors du **premier** consentement (sauf si la requête d'autorisation inclut `prompt=consent` côté client) — à garder en tête lors de l'implémentation du flow Flutter.

### Endpoints (`/api/v1/calendar`) — nécessitent un token Bearer

| Méthode | Route | Description |
|---|---|---|
| POST | `/connect/callback` | Finalise la connexion Google Calendar (échange du code OAuth) |
| GET | `/connect/status` | Indique si le compte Google est connecté |
| DELETE | `/connect` | Déconnecte le compte Google (supprime les tokens stockés) |
| POST | `/` | Crée un événement (retourne les conflits détectés, sans bloquer la création) |
| GET | `/` | Liste les événements (filtres `start_range`/`end_range`, par défaut : 30 prochains jours) |
| PATCH | `/{event_id}` | Met à jour/reporte un événement |
| DELETE | `/{event_id}` | Supprime un événement |

### Sécurité et dégradation gracieuse

- Les tokens OAuth sont **chiffrés au repos** (`src/core/encryption.py`, Fernet) — jamais stockés en clair, conformément au §11 du document d'architecture.
- Les événements sont mis en cache localement (table `calendar_events`) : la lecture (`GET /`) ne dépend donc pas de la disponibilité de Google Calendar.
- Si l'utilisateur n'a pas encore connecté son compte Google, la création d'événement fonctionne quand même (persistée localement uniquement, `synced=false`) plutôt que d'échouer.

### Intégration dans l'orchestrateur d'agents

Le router LangGraph reconnaît désormais 3 intentions (`task`, `calendar`, `chat`). L'agent Agenda (`calendar_agent_node.py`) utilise le function calling Mistral avec 3 outils : `calendar_create`, `calendar_list`, `calendar_delete` (ce dernier classé sensible, nécessite confirmation — voir `SENSITIVE_CALENDAR_TOOLS`).

```bash
curl -X POST http://localhost:8000/api/v1/conversation/message \
  -H "Authorization: Bearer <votre_access_token>" \
  -H "Content-Type: application/json" \
  -d '{"content": "Ajoute un rendez-vous demain à 14h avec le client Dupont jusqu'\''à 15h"}'
```

## Module Mémoire long terme (pgvector)

Chaque tour de conversation (texte ou vocal) déclenche automatiquement :

1. **Chargement** (`memory_load_node`, premier node du graphe) : recherche par similarité cosinus des 5 souvenirs les plus pertinents par rapport au dernier message utilisateur, via `mistral-embed`.
2. **Injection** : les souvenirs trouvés sont insérés dans le prompt système de l'agent conversationnel (`chat_agent_node`), pour personnaliser la réponse.
3. **Écriture** (`memory_write_node`, dernier node avant `END`) : extrait via un appel LLM léger les informations durables révélées dans l'échange du tour (pas tout l'historique), et les mémorise automatiquement. Toutes les branches du graphe (chat, tâches, agenda) convergent vers ce node avant de se terminer.

> ⚠️ **Compromis assumé** : l'écriture mémoire est synchrone dans le graphe, donc elle ajoute un appel LLM (et de la latence) à chaque tour de conversation, y compris vocale. Une version V3 pourra la déporter en tâche de fond pour ne plus impacter la latence perçue — non fait ici pour éviter les effets de bord d'une tâche détachée sur la durée de vie de la session DB (voir commentaire dans `memory_write_node.py`).

Types de souvenirs (`MemoryType`) : `fact`, `preference`, `habit`, `goal`, `conversation_summary`. Ces derniers expirent automatiquement après 90 jours (`Memory.default_expiry_for`) pour limiter la croissance de la mémoire — les autres types sont conservés indéfiniment.

`ConsolidateConversationMemoryUseCase` reste disponible pour résumer une conversation complète a posteriori (ex. appelé par un job scheduler en fin de session), complémentaire à l'extraction légère faite par `memory_write_node` à chaque tour.

## Réveil intelligent (scheduler)

Le scheduler (`src/infrastructure/scheduler/proactive_jobs.py`, APScheduler) démarre automatiquement avec l'application (`lifespan` FastAPI) et vérifie chaque minute, **pour chaque utilisateur, dans son fuseau horaire propre** (`User.timezone`, ex. `Europe/Paris`), si l'heure locale correspond à son heure de briefing configurée (`UserSettings.briefing_time`, interprétée comme une heure locale). Si c'est le cas, il génère le briefing (`GenerateMorningBriefingUseCase`, qui agrège les tâches urgentes et les événements du jour) et le stocke comme notification.

La conversion de fuseau horaire utilise `zoneinfo` (bibliothèque standard Python, aucune dépendance supplémentaire) ; un fuseau invalide ou inconnu bascule silencieusement sur UTC avec un log d'avertissement plutôt que de faire échouer le scheduler pour tous les utilisateurs.

### Endpoints Paramètres (`/api/v1/settings`) — nécessitent un token Bearer

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/settings` | Paramètres de l'utilisateur (valeurs par défaut si jamais configurés) |
| PUT | `/api/v1/settings` | Met à jour les paramètres (voix, volume, heure de briefing, thème, langue, niveau d'autonomie) |

### Endpoints Notifications (`/api/v1/notifications`) — nécessitent un token Bearer

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/v1/notifications` | Liste les notifications (filtre `unread_only`) |
| POST | `/api/v1/notifications/{id}/read` | Marque une notification comme lue |

Tester le réveil intelligent rapidement : configurer `briefing_time` à l'heure UTC courante + 1 minute via `PUT /api/v1/settings`, attendre, puis consulter `GET /api/v1/notifications`.

## Prochaines étapes

Le backend V2 est désormais fonctionnellement complet. Pour la V3, conformément à la roadmap du document d'architecture :

1. **Écriture mémoire asynchrone** : déporter `memory_write_node` en tâche de fond pour ne plus impacter la latence de réponse (actuellement synchrone, voir §Module Mémoire ci-dessus)
2. **Intégration RAG documentaire** (ingestion, `pgvector` déjà en place pour la mémoire, réutilisable pour les documents)
3. **Intégration Gmail** : e-mails importants dans le briefing matinal (actuellement absent, voir TODO dans `generate_morning_briefing.py`)
4. **Intégration météo** dans le briefing matinal (voir même TODO)
5. **Synchronisation Google Calendar bidirectionnelle** : webhooks push notifications pour détecter les modifications faites directement dans Google Calendar
6. **Boucle multi-outils** : les agents Tâches et Agenda ne traitent qu'un seul appel d'outil par tour (simplification V1/V2)
7. **Latence vocale** : transcription incrémentale par VAD, découpage du TTS phrase par phrase (§10.2)
8. **Scheduler à l'échelle** : passer d'un polling toutes-les-minutes-tous-utilisateurs à un job dédié par utilisateur si le volume le justifie
9. **Application Flutter** : connexion à l'ensemble des endpoints désormais disponibles (Auth, Tâches, Agenda, Conversation, Voix, Paramètres, Notifications) — **prochaine étape immédiate**

Voir le document d'architecture complet (`W4FO_Architecture.md`) pour le détail de chaque module et les diagrammes associés.
