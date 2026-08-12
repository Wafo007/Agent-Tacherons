import '../entities/conversation_message.dart';
import '../repositories/conversation_repository.dart';

/// Use case : envoie un message à l'orchestrateur d'agents et retourne le résultat.
class SendVoiceMessage {
  final ConversationRepository _repository;

  const SendVoiceMessage(this._repository);

  Future<ConversationResult> call(String content, List<ConversationMessage> history) {
    return _repository.sendMessage(content, history);
  }
}
