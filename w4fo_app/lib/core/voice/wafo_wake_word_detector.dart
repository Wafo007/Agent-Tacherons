import 'dart:async';

import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'wake_word_detector.dart';

/// Implémentation concrète de [WakeWordDetector] pour le mot-clé de réveil
/// par défaut de W4FO : **"Wafo"**.
///
/// ## Choix technique
///
/// S'appuie sur le package `speech_to_text`, qui encapsule le moteur de
/// reconnaissance vocale **natif de l'OS** (`android.speech.SpeechRecognizer`
/// côté Android, `Speech` framework côté iOS). Ce choix a été préféré à un
/// moteur Wake Word dédié (type Porcupine/Vosk) pour respecter les
/// priorités du projet :
///
/// - **Stabilité / compatibilité Android** : plugin Flutter mature, aucun
///   binaire natif (.so) supplémentaire à embarquer, aucune clé d'accès
///   tierce à gérer, aucune recompilation native requise sur Windows (donc
///   aucun risque de réintroduire une dépendance à Visual C++).
/// - **Faible consommation** : le moteur de reconnaissance est celui déjà
///   fourni par l'OS (souvent accéléré/optimisé nativement, avec support
///   hors-ligne sur beaucoup d'appareils Android récents), pas de modèle ML
///   embarqué à charger/exécuter nous-mêmes.
/// - **Maintenabilité** : une seule dépendance Dart supplémentaire, pas de
///   pipeline audio bas niveau custom à maintenir.
///
/// ## Fonctionnement
///
/// Le moteur natif fonctionne par sessions (il s'arrête après un silence).
/// Pour simuler une écoute passive continue tant que [isActive] est vrai,
/// chaque session terminée relance automatiquement une nouvelle session
/// d'écoute (`_listenOnce`). Dès que le texte reconnu contient le mot-clé
/// (["wafo"] par défaut, insensible à la casse), un événement est émis sur
/// [onWakeWordDetected] et la session en cours est arrêtée : c'est ensuite
/// à l'appelant ([VoiceChatNotifier.enableWakeWord]) de démarrer la capture
/// de commande réelle via le pipeline existant.
///
/// ## Garantie "pas de streaming vers Mistral"
///
/// Cette classe ne communique avec aucun serveur : elle appelle uniquement
/// l'API locale `speech_to_text` de l'appareil. Aucun appel réseau, aucun
/// envoi à Mistral ou au WebSocket vocal backend n'a lieu tant que le
/// mot-clé n'a pas été détecté.
class WafoWakeWordDetector implements WakeWordDetector {
  /// Mot-clé de réveil recherché dans le texte reconnu (comparaison en
  /// minuscules, "contains" pour tolérer les mots environnants captés par
  /// le moteur STT, ex. "wafo organise mes tâches").
  final String wakeWord;

  /// Langue utilisée par le moteur de reconnaissance. Français par défaut,
  /// cohérent avec le reste de l'app.
  final String localeId;

  final stt.SpeechToText _speech;
  final StreamController<void> _controller = StreamController<void>.broadcast();

  bool _active = false;
  bool _initialized = false;
  bool _sessionInFlight = false;

  WafoWakeWordDetector({
    this.wakeWord = 'wafo',
    this.localeId = 'fr_FR',
    stt.SpeechToText? speechToText,
  }) : _speech = speechToText ?? stt.SpeechToText();

  @override
  Stream<void> get onWakeWordDetected => _controller.stream;

  @override
  bool get isActive => _active;

  Future<bool> _ensureInitialized() async {
    if (_initialized) return true;
    try {
      _initialized = await _speech.initialize(
        onStatus: _onStatus,
        // Les erreurs transitoires (timeout, pas de correspondance, micro
        // momentanément indisponible) ne doivent jamais faire planter la
        // boucle d'écoute passive : on les ignore silencieusement et on
        // relance une session via _onStatus.
        onError: (_) {},
      );
    } catch (_) {
      _initialized = false;
    }
    return _initialized;
  }

  @override
  Future<void> start() async {
    if (_active) return;
    final ok = await _ensureInitialized();
    if (!ok) return;
    _active = true;
    unawaited(_listenOnce());
  }

  Future<void> _listenOnce() async {
    if (!_active || _sessionInFlight) return;
    _sessionInFlight = true;
    try {
      await _speech.listen(
        onResult: _onResult,
        localeId: localeId,
        // Fenêtres courtes et un pauseFor modéré : suffisant pour capter le
        // mot-clé sans garder le micro "chaud" trop longtemps entre deux
        // sessions, ce qui limite la consommation.
        listenFor: const Duration(seconds: 25),
        pauseFor: const Duration(seconds: 4),
        partialResults: true,
        cancelOnError: false,
        listenMode: stt.ListenMode.confirmation,
      );
    } catch (_) {
      // Session STT indisponible (permission retirée entre-temps, etc.) :
      // on abandonne cette tentative, _onStatus/le prochain start() gérera
      // une éventuelle relance.
    } finally {
      _sessionInFlight = false;
    }
  }

  void _onResult(SpeechRecognitionResult result) {
    final text = result.recognizedWords.toLowerCase();
    if (text.contains(wakeWord)) {
      _controller.add(null);
      // On arrête immédiatement cette session : l'appelant va basculer sur
      // la capture de commande réelle et mettra ce détecteur en pause via
      // stop() pour libérer le micro.
      unawaited(_speech.stop());
    }
  }

  void _onStatus(String status) {
    // Les sessions du moteur natif se terminent après un silence ou un
    // timeout ('done'/'notListening'). Tant que l'écoute passive doit
    // rester active, on relance une nouvelle session pour émuler une
    // écoute continue du mot-clé.
    if ((status == 'done' || status == 'notListening') && _active) {
      Future.delayed(const Duration(milliseconds: 300), _listenOnce);
    }
  }

  @override
  Future<void> stop() async {
    _active = false;
    await _speech.stop();
  }

  @override
  Future<void> dispose() async {
    _active = false;
    await _speech.cancel();
    await _controller.close();
  }
}
