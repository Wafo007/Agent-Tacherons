import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../constants/app_constants.dart';

/// Événements reçus du serveur sur le canal vocal (voir `voice_ws.py` côté backend).
sealed class VoiceServerEvent {
  const VoiceServerEvent();
}

class TranscriptEvent extends VoiceServerEvent {
  final String text;
  const TranscriptEvent(this.text);
}

class AgentThinkingEvent extends VoiceServerEvent {
  const AgentThinkingEvent();
}

/// Un mot de la réponse, à afficher au moment précis (§ TEXTE PROGRESSIF) où
/// l'audio le prononce. [offsetMs]/[durationMs] sont exprimés en
/// millisecondes DEPUIS LE DÉBUT de la synthèse de cette réponse (donc
/// depuis le début de la lecture audio côté client) — voir
/// `EdgeTTSProvider` côté backend, qui fournit ce timing nativement (pas une
/// reconstruction approximative).
class ResponseWordEvent extends VoiceServerEvent {
  final String text;
  final int offsetMs;
  final int durationMs;
  const ResponseWordEvent(this.text, this.offsetMs, this.durationMs);
}

/// Texte complet de la réponse, envoyé par le serveur juste avant
/// `end_of_turn`, UNIQUEMENT pour réconcilier l'historique de conversation
/// (le message final enregistré doit être exactement le texte source, pas
/// une reconstruction à partir des mots reçus un par un). Ne doit JAMAIS
/// être utilisé pour un affichage "d'un bloc" — voir
/// `VoiceChatNotifier._handleServerEvent`, qui l'utilise seulement pour
/// finaliser le message déjà affiché progressivement via [ResponseWordEvent].
class ResponseTextFinalEvent extends VoiceServerEvent {
  final String text;
  const ResponseTextFinalEvent(this.text);
}

/// Résumé (rétrospectif — voir limitation documentée dans le rapport de
/// livraison) des outils exécutés par l'agent durant ce tour.
class ToolCallsSummaryEvent extends VoiceServerEvent {
  final List<Map<String, dynamic>> tools;
  const ToolCallsSummaryEvent(this.tools);
}

/// La fenêtre de capture de commande a expiré sans qu'aucun `end_of_speech`
/// n'ait été reçu par le serveur (§ INTERRUPTION : timeout).
class CommandTimeoutEvent extends VoiceServerEvent {
  const CommandTimeoutEvent();
}

/// Le serveur confirme qu'un `interrupt` envoyé par le client a bien annulé
/// le traitement ou la lecture en cours (barge-in réel, § INTERRUPTION).
class InterruptedEvent extends VoiceServerEvent {
  const InterruptedEvent();
}

class RequiresConfirmationEvent extends VoiceServerEvent {
  final Map<String, dynamic> toolCall;
  const RequiresConfirmationEvent(this.toolCall);
}

/// Action applicative déclenchée par l'agent (§ ACTION GATEWAY côté backend),
/// ex: navigation vers un écran. `action` est un code fermé (ex: "OPEN_TASKS")
/// — voir `VoiceChatNotifier._handleClientAction` pour la liste exacte des
/// codes reconnus côté client : tout code inconnu est ignoré, jamais exécuté
/// à l'aveugle.
class ClientActionEvent extends VoiceServerEvent {
  final String action;
  final Map<String, dynamic> payload;
  const ClientActionEvent(this.action, this.payload);
}

class EndOfTurnEvent extends VoiceServerEvent {
  const EndOfTurnEvent();
}

class AudioChunkEvent extends VoiceServerEvent {
  final Uint8List data;
  const AudioChunkEvent(this.data);
}

/// Client WebSocket bas niveau pour le canal vocal `/ws/v1/voice`.
///
/// Implémente exactement le protocole décrit au §10.1/§10.2 du document
/// d'architecture : frames binaires = audio, frames texte JSON = contrôle.
/// Cette classe ne connaît rien du domaine métier (Task, Conversation...) —
/// elle expose un flux d'événements bas niveau, consommé par
/// `VoiceChatRepository` puis par le provider Riverpod `voice_chat_provider.dart`.
class VoiceWebSocketClient {
  WebSocketChannel? _channel;
  final _eventController = StreamController<VoiceServerEvent>.broadcast();

  Stream<VoiceServerEvent> get events => _eventController.stream;

  Future<void> connect({required String accessToken, String voiceId = 'default'}) async {
    final uri = Uri.parse(
      '${AppConstants.wsBaseUrl}/ws/v1/voice?token=$accessToken&voice_id=$voiceId',
    );
    _channel = WebSocketChannel.connect(uri);

    _channel!.stream.listen(
      _handleIncomingMessage,
      onError: (error) => _eventController.addError(error),
      onDone: () => _eventController.close(),
      cancelOnError: false,
    );
  }

  void _handleIncomingMessage(dynamic message) {
    if (message is List<int>) {
      _eventController.add(AudioChunkEvent(Uint8List.fromList(message)));
      return;
    }

    if (message is String) {
      final decoded = jsonDecode(message) as Map<String, dynamic>;
      switch (decoded['event']) {
        case 'transcript':
          _eventController.add(TranscriptEvent(decoded['text'] as String? ?? ''));
        case 'agent_thinking':
          _eventController.add(const AgentThinkingEvent());
        case 'response_word':
          _eventController.add(
            ResponseWordEvent(
              decoded['text'] as String? ?? '',
              decoded['offset_ms'] as int? ?? 0,
              decoded['duration_ms'] as int? ?? 0,
            ),
          );
        case 'response_text_final':
          _eventController.add(ResponseTextFinalEvent(decoded['text'] as String? ?? ''));
        case 'tool_calls_summary':
          final tools = (decoded['tools'] as List<dynamic>? ?? [])
              .whereType<Map<String, dynamic>>()
              .toList(growable: false);
          _eventController.add(ToolCallsSummaryEvent(tools));
        case 'command_timeout':
          _eventController.add(const CommandTimeoutEvent());
        case 'interrupted':
          _eventController.add(const InterruptedEvent());
        case 'requires_confirmation':
          _eventController.add(
            RequiresConfirmationEvent(decoded['tool_call'] as Map<String, dynamic>? ?? {}),
          );
        case 'client_action':
          final action = decoded['action'] as String?;
          if (action != null && action.isNotEmpty) {
            _eventController.add(
              ClientActionEvent(action, decoded['payload'] as Map<String, dynamic>? ?? {}),
            );
          }
        case 'end_of_turn':
          _eventController.add(const EndOfTurnEvent());
      }
    }
  }

  /// Envoie un chunk audio brut capturé depuis le micro (frame binaire).
  void sendAudioChunk(Uint8List chunk) {
    _channel?.sink.add(chunk);
  }

  /// Signale la fin du segment de parole de l'utilisateur.
  ///
  /// [whatsappContext], si fourni, attache le message WhatsApp actuellement
  /// en attente de réponse (§ CONTEXTE, séparation des contextes — voir
  /// `voice_ws.py` côté backend et `WhatsAppNotifier` côté client, seul
  /// appelant qui renseigne ce paramètre). `null` dans tous les autres cas :
  /// aucun changement de comportement pour une commande vocale classique.
  void sendEndOfSpeech({Map<String, String>? whatsappContext}) {
    final payload = <String, dynamic>{'event': 'end_of_speech'};
    if (whatsappContext != null) {
      payload['whatsapp_context'] = whatsappContext;
    }
    _channel?.sink.add(jsonEncode(payload));
  }

  /// Barge-in : interrompt la réponse en cours de lecture côté serveur.
  void sendInterrupt() {
    _channel?.sink.add(jsonEncode({'event': 'interrupt'}));
  }

  Future<void> disconnect() async {
    await _channel?.sink.close();
    await _eventController.close();
  }
}
