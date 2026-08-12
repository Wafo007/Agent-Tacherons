import '../entities/conversation_message.dart';

/// Résultat du traitement d'un message par l'orchestrateur d'agents backend.
class ConversationResult {
  final String response;
  final bool requiresConfirmation;
  final Map<String, dynamic>? pendingToolCall;

  const ConversationResult({required this.response, this.requiresConfirmation = false, this.pendingToolCall});
}

/// Interface (Port) : ConversationRepository.
///
/// Couvre le mode texte (REST, `POST /api/v1/conversation/message`). Le mode
/// vocal (WebSocket) est couvert séparément par `VoiceChatDataSource`, car son
/// contrat (flux bidirectionnel audio + événements) ne se prête pas au même
/// pattern request/response qu'un repository classique.
abstract class ConversationRepository {
  Future<ConversationResult> sendMessage(String content, List<ConversationMessage> history);
}
