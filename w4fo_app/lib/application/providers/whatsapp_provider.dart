import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../../core/whatsapp/whatsapp_controller.dart';

/// Un échange WhatsApp local (reçu ou envoyé par W4FO), pour affichage dans
/// l'écran dédié (§ CONTEXTE : conversation WhatsApp séparée de la
/// conversation Flutter/voix — jamais mélangée à `VoiceChatState.messages`).
class WhatsAppExchange {
  final String sender;
  final String text;
  final bool isReplyFromW4FO;
  final DateTime timestamp;

  WhatsAppExchange({
    required this.sender,
    required this.text,
    required this.isReplyFromW4FO,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}

class WhatsAppState {
  final bool listeningEnabled;
  final bool hasNotificationAccess;

  /// Le dernier message WhatsApp reçu, en attente d'une éventuelle réponse
  /// (§ CONTEXTE — contexte transitoire, consommé/effacé dès qu'une réponse
  /// est envoyée ou qu'un nouveau message arrive).
  final WhatsAppMessage? pendingMessage;

  final List<WhatsAppExchange> history;
  final String? lastError;

  const WhatsAppState({
    this.listeningEnabled = false,
    this.hasNotificationAccess = false,
    this.pendingMessage,
    this.history = const [],
    this.lastError,
  });

  WhatsAppState copyWith({
    bool? listeningEnabled,
    bool? hasNotificationAccess,
    WhatsAppMessage? pendingMessage,
    bool clearPendingMessage = false,
    List<WhatsAppExchange>? history,
    String? lastError,
  }) {
    return WhatsAppState(
      listeningEnabled: listeningEnabled ?? this.listeningEnabled,
      hasNotificationAccess: hasNotificationAccess ?? this.hasNotificationAccess,
      pendingMessage: clearPendingMessage ? null : (pendingMessage ?? this.pendingMessage),
      history: history ?? this.history,
      lastError: lastError,
    );
  }
}

/// Orchestre la lecture et la réponse aux messages WhatsApp (§ WHATSAPP du
/// brief), entièrement on-device (voir `core/whatsapp/README.md` pour
/// l'architecture complète et ses limites assumées).
///
/// § CONTEXTE (séparation) : ce notifier possède SA PROPRE conversation
/// (`state.history`), jamais mélangée à `VoiceChatState.messages` (conversation
/// Flutter/voix), à la mémoire utilisateur, ni aux contextes Task/Calendar.
/// La seule passerelle entre les deux est volontairement étroite et
/// transitoire : [consumePendingContextForNextCommand], lu par
/// `VoiceChatNotifier` au moment d'envoyer `end_of_speech`, qui attache le
/// message en attente pour CE tour seulement (voir `voice_ws.py`).
class WhatsAppNotifier extends StateNotifier<WhatsAppState> {
  final WhatsAppController _controller;
  final FlutterTts _tts;
  StreamSubscription<WhatsAppMessage>? _subscription;

  WhatsAppNotifier({WhatsAppController? controller, FlutterTts? tts})
      : _controller = controller ?? WhatsAppController(),
        _tts = tts ?? FlutterTts(),
        super(const WhatsAppState()) {
    _tts.setLanguage('fr-FR');
  }

  /// Vérifie l'état actuel de la permission système (à appeler notamment au
  /// retour dans l'app après [requestNotificationAccess], qui ouvre un écran
  /// système sans callback de résultat direct).
  Future<void> refreshPermissionStatus() async {
    final granted = await _controller.hasNotificationAccess();
    state = state.copyWith(hasNotificationAccess: granted);
  }

  Future<void> requestNotificationAccess() => _controller.openNotificationAccessSettings();

  /// Active la lecture/réponse WhatsApp. Nécessite que la permission
  /// d'accès aux notifications ait déjà été accordée (voir
  /// [refreshPermissionStatus]) — sinon le service natif ne reçoit tout
  /// simplement aucune notification à traiter, mais l'app ne plante pas.
  Future<void> enable() async {
    await _controller.setListeningEnabled(true);
    await _subscription?.cancel();
    _subscription = _controller.messages.listen(_handleIncomingMessage, onError: (_) {
      state = state.copyWith(lastError: 'Connexion au service WhatsApp interrompue.');
    });
    state = state.copyWith(listeningEnabled: true, lastError: null);
  }

  Future<void> disable() async {
    await _controller.setListeningEnabled(false);
    await _subscription?.cancel();
    _subscription = null;
    state = state.copyWith(listeningEnabled: false, clearPendingMessage: true);
  }

  Future<void> _handleIncomingMessage(WhatsAppMessage message) async {
    state = state.copyWith(
      pendingMessage: message.canReply ? message : null,
      history: [
        ...state.history,
        WhatsAppExchange(sender: message.sender, text: message.text, isReplyFromW4FO: false),
      ],
    );

    final announcement = message.canReply
        ? "Message WhatsApp de ${message.sender} : ${message.text}. Dis Wafo pour répondre."
        : "Message WhatsApp de ${message.sender} : ${message.text}.";
    try {
      await _tts.stop();
      await _tts.speak(announcement);
    } catch (_) {
      // La synthèse vocale locale n'est qu'une commodité (le message reste
      // visible dans `state.history` de toute façon) : un échec ici ne doit
      // jamais empêcher la réception/l'affichage du message.
    }
  }

  /// À appeler par `VoiceChatNotifier` juste avant d'envoyer `end_of_speech`
  /// (§ CONTEXTE) : retourne le contexte du message WhatsApp en attente, à
  /// joindre à CE tour de commande vocale uniquement. Ne l'efface PAS lui-même
  /// — le contexte n'est consommé (effacé) que lorsque l'agent envoie
  /// effectivement une réponse (voir [sendReply]), afin qu'une commande vocale
  /// sans rapport avec WhatsApp ("crée une tâche...") n'invalide pas le
  /// contexte pour la commande suivante.
  Map<String, String>? consumePendingContextForNextCommand() {
    final pending = state.pendingMessage;
    if (pending == null) return null;
    return {'sender': pending.sender, 'text': pending.text};
  }

  /// Envoie [text] comme réponse au message en attente — appelé par
  /// `VoiceChatNotifier` en réaction au `client_action` `WHATSAPP_REPLY`
  /// renvoyé par l'agent (voir `whatsapp_tools.py` côté backend).
  Future<bool> sendReply(String text) async {
    final pending = state.pendingMessage;
    final success = await _controller.sendReply(text);
    if (success) {
      state = state.copyWith(
        clearPendingMessage: true,
        history: [
          ...state.history,
          WhatsAppExchange(sender: pending?.sender ?? '', text: text, isReplyFromW4FO: true),
        ],
      );
    } else {
      state = state.copyWith(
        lastError: "Impossible d'envoyer la réponse WhatsApp (message expiré ou action indisponible).",
      );
    }
    return success;
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _tts.stop();
    super.dispose();
  }
}

final whatsAppProvider = StateNotifierProvider<WhatsAppNotifier, WhatsAppState>(
  (ref) => WhatsAppNotifier(),
);
