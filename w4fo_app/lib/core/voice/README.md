# Architecture vocale W4FO — Wake Word "Wafo"

## État : implémenté (écoute en premier plan uniquement)

Le Wake Word local est maintenant actif : quand l'écran vocal est ouvert et
connecté, W4FO écoute passivement le mot-clé **"Wafo"** et démarre
automatiquement la capture de commande dès qu'il est détecté.

## Cycle complet

```
IDLE
  ↓
LISTENING_FOR_WAKE_WORD   (écoute passive locale, aucun envoi réseau)
  ↓
WAKE_WORD_DETECTED        ("Wafo" reconnu par le moteur STT natif de l'OS)
  ↓
LISTENING_COMMAND         (micro → WebSocket, pipeline existant inchangé)
  ↓
PROCESSING                (STT distant, orchestrateur d'agents, TTS)
  ↓
RESPONSE                  (lecture de la réponse vocale)
  ↓
LISTENING_FOR_WAKE_WORD   (retour automatique à l'écoute du mot-clé)
```

Modélisé par `WakeWordPipelineState` (`wake_word_pipeline_state.dart`), en
plus du macro-état générique `VoiceEngineState` (`voice_engine_state.dart`)
introduit précédemment.

## Fichiers

- `voice_engine_state.dart` — macro-états génériques (IDLE, LISTENING,
  RECORDING_COMMAND, PROCESSING, SPEAKING, ERROR).
- `wake_word_pipeline_state.dart` — les 6 états du cycle Wake Word demandé,
  dérivés de `VoiceEngineState` + de l'indicateur `wakeWordActive`.
- `wake_word_detector.dart` — interface `WakeWordDetector` +
  `NoOpWakeWordDetector` (détecteur neutre, utilisé par défaut si aucun
  Wake Word n'est activé).
- `wafo_wake_word_detector.dart` — **implémentation réelle** du mot-clé
  "Wafo", basée sur `speech_to_text` (moteur de reconnaissance vocale natif
  de l'OS, 100% local).
- `passive_listening_service.dart` — interface pour un futur conteneur
  d'écoute passive de plus haut niveau (non utilisée pour l'instant :
  `WafoWakeWordDetector` implémente directement `WakeWordDetector`).

## Choix technique : pourquoi `speech_to_text`

Analyse des alternatives (Porcupine, Vosk, faster-whisper/ctranslate2) :
toutes nécessitent soit une clé d'accès tierce et un entraînement custom du
mot-clé (Porcupine), soit un modèle embarqué à charger (Vosk), soit une
dépendance native lourde explicitement interdite par la consigne
(faster-whisper/ctranslate2). `speech_to_text` :

- s'appuie sur le moteur natif de l'OS (Android `SpeechRecognizer`, souvent
  disponible hors-ligne sur les appareils récents) ;
- n'ajoute aucun binaire natif, aucune clé d'accès, aucune compilation C++
  supplémentaire (donc aucun risque de réintroduire une dépendance à
  Visual C++, notamment pour un futur portage Windows) ;
- reste une dépendance Dart légère et largement maintenue.

`SpeechRecognition` côté backend n'a pas été touché : `speech_to_text`
n'intervient que côté client, pour la détection locale du mot-clé, jamais
pour la transcription de la commande elle-même (qui reste gérée par le
pipeline WebSocket existant → `stt_provider_impl.py`).

## Garantie "pas de streaming vers Mistral"

`WafoWakeWordDetector` n'ouvre aucune connexion réseau. Il appelle
uniquement l'API locale du moteur de reconnaissance vocale de l'appareil.
Le WebSocket vocal (`VoiceWebSocketClient`) et donc l'accès à Mistral ne
sont sollicités qu'après détection du mot-clé, via l'appel à
`startListening()` — le pipeline de capture de commande déjà existant et
inchangé.

## Coordination avec la capture de commande (pas de conflit micro)

`VoiceChatNotifier` :

- met l'écoute passive en pause dès que `startListening()` démarre (qu'elle
  soit déclenchée par le Wake Word ou par appui manuel sur le bouton) ;
- la relance automatiquement dès le retour à `idle` (`end_of_turn`,
  transcript vide, ou interruption barge-in) ;
- expose `pauseWakeWordForBackground()` / `resumeWakeWordFromBackground()`,
  câblés sur le cycle de vie de l'app (`WidgetsBindingObserver` dans
  `voice_chat_screen.dart`) : l'écoute passive est mise en pause dès que
  l'app quitte le premier plan, conformément aux restrictions Android
  modernes sur l'accès micro en arrière-plan, et reprise au retour au
  premier plan.

## Ce qui n'est PAS fait ici (volontairement, hors périmètre)

- Pas de service Android **Always-On** complet (foreground service avec
  notification persistante, écoute alors que l'app est totalement fermée).
  Le Wake Word ne fonctionne aujourd'hui que lorsque l'écran vocal est
  ouvert et l'app au premier plan — c'est un choix délibéré pour rester
  dans les limites de ce chantier et respecter les restrictions Android
  modernes sur l'accès micro en arrière-plan.
- Les permissions liées à un futur service persistant
  (`FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MICROPHONE`,
  `POST_NOTIFICATIONS`) n'ont pas été demandées : elles ne seraient pas
  utilisées aujourd'hui, et une app ne doit demander que les permissions
  dont elle a un usage réel immédiat.
- `SpeechRecognition` côté backend n'est pas remplacé par
  `faster-whisper`/`ctranslate2`.
- Aucune dépendance native lourde ajoutée ; aucune réintroduction de
  Visual C++.
- WhatsApp non touché.

## Bug corrigé au passage

`android/app/src/main/res/AndroidManifest.xml` était un fichier mal placé
(AAPT ne lit le manifeste que depuis `android/app/src/main/AndroidManifest.xml`,
jamais depuis `res/`) : son contenu (permissions micro, label "W4FO")
n'était donc jamais réellement appliqué au build, et sa présence dans `res/`
risquait de faire échouer la compilation des ressources. Son contenu utile
a été fusionné dans le vrai manifeste, et le fichier erroné supprimé.
