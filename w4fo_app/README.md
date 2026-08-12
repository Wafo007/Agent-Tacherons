# W4FO — Application Flutter

Application mobile (Android, portage Windows prévu) de l'assistant IA personnel **W4FO**, construite en **Clean Architecture**, connectée au [backend W4FO](../w4fo-backend).

> Ce projet correspond à l'étape V1 du frontend : authentification, conversation vocale temps réel, gestion des tâches, agenda, paramètres. Voir "Limitations connues" en fin de document pour ce qui reste à faire.

## Architecture

Même principe que le backend : les dépendances pointent vers le domaine.

```
presentation  →  application  →  domain  ←  data
```

- **`domain/`** : entités pures (`Task`, `CalendarEvent`, `ConversationMessage`, `User`), interfaces repository, use cases. Aucune dépendance Flutter/HTTP.
- **`data/`** : implémentations concrètes — modèles JSON, datasources REST (Dio), stockage sécurisé (tokens JWT).
- **`application/`** : gestion d'état avec Riverpod (`StateNotifier` + `StateNotifierProvider`) — équivalent des "use cases orchestrés" côté backend.
- **`presentation/`** : écrans et widgets, organisés par fonctionnalité (`features/auth`, `features/voice_chat`, `features/tasks`, `features/calendar`, `features/settings`).
- **`core/`** : configuration réseau (client Dio + client WebSocket), thème, router (go_router), injection de dépendances Riverpod.

Le fichier `core/di/injection.dart` est l'unique point de câblage entre interfaces de domaine et implémentations concrètes — en miroir direct de `dependencies.py` côté backend.

## Choix techniques

| Domaine | Choix | Justification |
|---|---|---|
| State management | **Riverpod** (`flutter_riverpod`) | Testable, pas de `BuildContext` requis dans la logique métier, DI intégrée |
| Navigation | **go_router** | Redirection déclarative selon l'état d'authentification, gestion propre des deep links |
| Réseau REST | **Dio** | Intercepteurs (JWT automatique), gestion d'erreurs centralisée |
| Réseau temps réel | **web_socket_channel** | Miroir direct du protocole `/ws/v1/voice` du backend |
| Stockage sécurisé | **flutter_secure_storage** | Tokens JWT jamais en `SharedPreferences` en clair |
| Audio | **record** (capture) + **just_audio** (lecture) | Couvre capture micro streamée et lecture de fichiers audio (MP3 reçus du backend) |
| Modèles JSON | Classes Dart manuelles (pas de Freezed/json_serializable) | Évite la dépendance à `build_runner`, non exécutable dans l'environnement de développement utilisé pour créer ce squelette — voir note ci-dessous |

> **Note sur Freezed** : le choix de classes manuelles plutôt que Freezed est pragmatique, pas définitif. Si le projet grossit, migrer vers Freezed pour l'immutabilité et le pattern matching est raisonnable — il faudra alors exécuter `flutter pub run build_runner build` après l'avoir ajouté aux dépendances.

## Installation

### Prérequis
- Flutter SDK ≥ 3.4.0 ([guide d'installation](https://docs.flutter.dev/get-started/install))
- Le [backend W4FO](../w4fo-backend) démarré (voir son propre README)
- Un émulateur Android, ou un appareil physique connecté

### Étapes

```bash
cd w4fo_app
flutter pub get
```

### Lancer l'application

```bash
# Backend en local sur localhost:8000 (valeur par défaut)
flutter run

# Backend à une autre adresse (ex. téléphone physique sur le même réseau que le PC de dev)
flutter run --dart-define=API_BASE_URL=http://192.168.1.42:8000 --dart-define=WS_BASE_URL=ws://192.168.1.42:8000
```

> ⚠️ Un émulateur Android accède à `localhost` de la machine hôte via `10.0.2.2`, pas `localhost` directement. Utilisez `--dart-define=API_BASE_URL=http://10.0.2.2:8000` dans ce cas.

## Structure des dossiers

```
lib/
├── core/
│   ├── di/injection.dart          # Câblage domaine ↔ implémentations (Riverpod)
│   ├── router/app_router.dart     # go_router + redirection selon l'auth
│   ├── theme/                     # Couleurs et thèmes clair/sombre
│   ├── constants/                 # URLs backend, clés de stockage
│   ├── errors/                    # Exceptions applicatives
│   └── network/                   # Client Dio (REST) + client WebSocket (voix)
├── domain/
│   ├── entities/                  # Task, CalendarEvent, ConversationMessage, User
│   ├── repositories/              # Interfaces (ports)
│   └── usecases/                  # GetTasks, SendVoiceMessage...
├── data/
│   ├── models/                    # Mapping JSON ↔ entités de domaine
│   ├── datasources/remote/        # Appels HTTP bruts vers chaque module backend
│   ├── datasources/local/         # Stockage sécurisé des tokens
│   └── repositories_impl/         # Implémentations concrètes des interfaces
├── application/
│   ├── providers/                 # StateNotifierProvider : auth, tasks, calendar, voice_chat, settings
│   └── state/                     # Classes d'état immutables (VoiceChatState...)
├── presentation/
│   ├── features/auth/             # Écrans login/register
│   ├── features/voice_chat/       # Écran principal : conversation vocale
│   ├── features/tasks/            # Liste + création de tâches
│   ├── features/calendar/         # Agenda + connexion Google
│   ├── features/settings/         # Paramètres utilisateur
│   └── shared_widgets/            # MainShell (navigation par onglets)
└── main.dart
```

## Écran de conversation vocale — flux détaillé

L'écran d'accueil (`voice_chat_screen.dart`) implémente le protocole défini côté backend (§10.1/§10.2 du document d'architecture) :

1. À l'ouverture, connexion WebSocket à `/ws/v1/voice?token=...` (`VoiceChatNotifier.connect()`).
2. Appui sur le bouton micro → capture audio streamée via `record` (`startListening()`), chunks envoyés en direct au serveur.
3. Relâchement du bouton → signal `end_of_speech` envoyé, phase `transcribing`.
4. Réception des événements serveur (`transcript`, `agent_thinking`, `response_text`, `requires_confirmation`) → mise à jour de `VoiceChatState`, reflétée dans l'UI (bulle de message, libellé de phase, bannière de confirmation).
5. Réception des chunks audio de la réponse → bufferisés, puis écrits dans un fichier temporaire et joués via `just_audio` une fois `end_of_turn` reçu.

### Limitation assumée (cohérente avec le backend)

La lecture audio ne démarre qu'une fois **tous** les chunks reçus (pas de lecture au fil de l'eau) — le backend lui-même n'envoie la réponse TTS qu'une fois le texte complet généré (pas de découpage phrase par phrase pour l'instant, voir README backend §10.2). Corriger les deux ensemble en V2 pour une latence perçue réduite.

## Limitations connues (V1)

1. **Flow OAuth Google Calendar non implémenté côté client** : le bouton de connexion dans l'écran Agenda affiche actuellement un message d'information plutôt que d'ouvrir le flow de consentement Google. Nécessite d'intégrer `google_sign_in` ou une webview dédiée, puis d'appeler `POST /api/v1/calendar/connect/callback` avec le code d'autorisation obtenu.
2. **Confirmation d'action sensible non actionnable** : l'écran vocal affiche la bannière de confirmation (`requires_confirmation`), mais aucune action n'est encore câblée pour renvoyer la confirmation au serveur — le backend lui-même documente cette même limitation côté WebSocket.
3. **Pas de mode hors-ligne** : toutes les données sont chargées depuis le serveur à chaque ouverture d'écran ; pas de cache local (prévu en V3 selon la roadmap du document d'architecture).
4. **Portage Windows non testé** : le dossier `windows/` existe mais n'a pas été généré via `flutter create --platforms=windows .` dans cet environnement (pas de Flutter SDK disponible pour le faire) — à faire en local avant le premier build Windows.
5. **Pas de tests automatisés** : contrairement au backend (tests unitaires sur le domaine), aucun test Flutter n'a encore été écrit — à ajouter, en particulier sur les `StateNotifier` (testables sans widget grâce à Riverpod).

## Prochaines étapes

1. Générer les projets natifs manquants : `flutter create --platforms=android,windows .` (nécessite le SDK Flutter, non disponible dans l'environnement ayant servi à créer ce squelette)
2. Implémenter le flow OAuth Google Calendar complet
3. Câbler le renvoi de confirmation d'action sensible (vocal + texte)
4. Ajouter les tests unitaires sur les providers Riverpod
5. Écran de briefing matinal dédié (actuellement, les notifications ne sont pas encore affichées dans l'app — endpoint backend déjà disponible : `GET /api/v1/notifications`)
