import 'dart:async';

import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'wake_word_detector.dart';

/// Implémentation concrète de [WakeWordDetector] pour le mot-clé de réveil
/// par défaut de W4FO : **"Wafo"**.
///
/// ## Choix technique — analyse de compatibilité (§ IMPORTANT du brief)
///
/// S'appuie sur le package `speech_to_text`, qui encapsule le moteur de
/// reconnaissance vocale **natif de l'OS** (`android.speech.SpeechRecognizer`
/// côté Android, `Speech` framework côté iOS).
///
/// **Ce moteur N'EST PAS un moteur de "wake word" au sens strict** (type
/// Porcupine, Snowboy, ou un modèle de keyword-spotting dédié) : il s'agit
/// d'un moteur de reconnaissance vocale généraliste, piloté par sessions
/// (il s'arrête après un silence, doit être relancé), avec une latence de
/// démarrage/arrêt de session notable et une consommation batterie plus
/// élevée qu'un moteur de spotting dédié optimisé pour tourner en continu à
/// très faible coût. Ce n'est donc PAS la solution idéale pour un Wake Word
/// "always-on" au sens strict — mais c'est un compromis DÉLIBÉRÉ compte tenu
/// des contraintes du projet :
///
/// - Porcupine (Picovoice) : nécessite une clé d'accès tierce (compte
///   Picovoice), un modèle `.ppn` entraîné spécifiquement pour "Wafo"
///   (payant au-delà d'un usage limité), et un binaire natif supplémentaire
///   par plateforme — rejeté ici faute de pouvoir vérifier la compatibilité
///   et le coût de licence dans ce contexte.
/// - Vosk : modèle embarqué à télécharger/empaqueter (dizaines de Mo),
///   toolchain de reconnaissance offline à intégrer — viable mais plus
///   lourd, non retenu pour cette itération sans pouvoir valider sa taille
///   et sa compatibilité Android réelles hors-ligne.
/// - faster-whisper/ctranslate2 : EXPLICITEMENT exclu par la consigne projet
///   (risque de dépendance à Visual C++ / compilation native complexe).
///
/// `speech_to_text` reste donc le choix retenu, avec les limites assumées
/// ci-dessus, et un durcissement anti-faux-positifs (voir plus bas) pour en
/// compenser en partie l'imprécision par rapport à un moteur dédié.
///
/// ## Anti-faux-positifs (§ ANTI-FAUX POSITIFS du brief)
///
/// Quatre mécanismes cumulatifs, tous nécessaires (aucun n'est suffisant
/// seul) :
/// 1. **Comparaison par frontière de mot** (regex `\bwafo\b`, texte
///    normalisé sans accents), pas une simple sous-chaîne : "wafo" ne
///    matche plus à l'intérieur d'un autre mot.
/// 2. **Résultats finaux uniquement** (`result.finalResult`) : les résultats
///    partiels du moteur STT sont bruités et changent plusieurs fois par
///    seconde — les ignorer élimine l'essentiel des déclenchements erratiques.
/// 3. **Seuil de confiance** (`result.confidence`) : un résultat final peu
///    fiable (bruit ambiant mal interprété) est ignoré. Le moteur retourne
///    parfois `1.0` par défaut quand la confiance n'est pas supportée par
///    la plateforme — dans ce cas précis (valeur exactement à 1.0 alors que
///    la plateforme ne la calcule pas réellement), le filtre ne peut pas
///    être plus strict que "ne pas bloquer".
/// 4. **Cooldown** : un mot-clé déjà déclenché ne peut pas re-déclencher une
///    seconde fois avant [cooldown] — évite les doubles activations sur un
///    résultat final suivi d'un correctif du moteur STT.
///
/// ## Fonctionnement
///
/// Le moteur natif fonctionne par sessions (il s'arrête après un silence).
/// Pour simuler une écoute passive continue tant que [isActive] est vrai,
/// chaque session terminée relance automatiquement une nouvelle session
/// d'écoute (`_listenOnce`). Dès qu'un résultat FINAL contient le mot-clé
/// (frontière de mot, confiance suffisante), un événement est émis sur
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
  /// Mot-clé de réveil recherché dans le texte reconnu (frontière de mot,
  /// insensible à la casse et aux accents — voir [_normalize]).
  final String wakeWord;

  /// Langue utilisée par le moteur de reconnaissance. Français par défaut,
  /// cohérent avec le reste de l'app.
  final String localeId;

  /// Confiance minimale (0.0–1.0) exigée sur un résultat final pour
  /// déclencher le mot-clé. Les plateformes qui ne calculent pas réellement
  /// la confiance renvoient souvent `1.0` par défaut (auquel cas ce filtre
  /// ne peut naturellement rien exclure) — ce n'est donc qu'une couche
  /// parmi les 4 décrites en tête de fichier, pas une garantie à elle seule.
  final double minConfidence;

  /// Délai minimal entre deux déclenchements successifs du mot-clé, pour
  /// éviter un double déclenchement sur un correctif du moteur STT.
  final Duration cooldown;

  final stt.SpeechToText _speech;
  final StreamController<void> _controller = StreamController<void>.broadcast();

  bool _active = false;
  bool _initialized = false;
  bool _sessionInFlight = false;
  DateTime? _lastTrigger;

  late final RegExp _wakeWordPattern;

  static const Map<String, String> _accentFold = {
    'à': 'a', 'â': 'a', 'ä': 'a',
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
    'î': 'i', 'ï': 'i',
    'ô': 'o', 'ö': 'o',
    'ù': 'u', 'û': 'u', 'ü': 'u',
    'ç': 'c',
  };

  WafoWakeWordDetector({
    this.wakeWord = 'wafo',
    this.localeId = 'fr_FR',
    this.minConfidence = 0.3,
    this.cooldown = const Duration(seconds: 2),
    stt.SpeechToText? speechToText,
  }) : _speech = speechToText ?? stt.SpeechToText() {
    _wakeWordPattern = RegExp(r'\b' + RegExp.escape(_normalize(wakeWord)) + r'\b');
  }

  @override
  Stream<void> get onWakeWordDetected => _controller.stream;

  @override
  bool get isActive => _active;

  /// Normalise un texte pour la comparaison : minuscules + suppression des
  /// accents courants (le moteur STT peut renvoyer "Wâfo" ou variantes selon
  /// le dialecte/l'accent de la personne).
  static String _normalize(String input) {
    var result = input.toLowerCase();
    _accentFold.forEach((accented, plain) {
      result = result.replaceAll(accented, plain);
    });
    return result;
  }

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
        // `partialResults: true` reste nécessaire pour que le moteur remonte
        // un résultat final propre en fin de segment ; [_onResult] ignore
        // néanmoins tout ce qui n'est pas `finalResult` (voir § anti-faux-positifs).
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
    // (1) Résultats finaux uniquement — voir § anti-faux-positifs.
    if (!result.finalResult) return;

    // (2) Frontière de mot, texte normalisé — pas une sous-chaîne brute.
    final text = _normalize(result.recognizedWords);
    if (!_wakeWordPattern.hasMatch(text)) return;

    // (3) Seuil de confiance (voir limitation documentée sur les plateformes
    // qui ne le calculent pas réellement, ci-dessus).
    if (result.confidence > 0 && result.confidence < minConfidence) return;

    // (4) Cooldown anti double-déclenchement.
    final now = DateTime.now();
    if (_lastTrigger != null && now.difference(_lastTrigger!) < cooldown) return;
    _lastTrigger = now;

    _controller.add(null);
    // On arrête immédiatement cette session : l'appelant va basculer sur
    // la capture de commande réelle et mettra ce détecteur en pause via
    // stop() pour libérer le micro.
    unawaited(_speech.stop());
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
