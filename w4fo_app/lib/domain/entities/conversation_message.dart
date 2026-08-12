import 'package:equatable/equatable.dart';

/// Rôle d'un message dans une conversation, aligné sur le format Mistral (role/content).
enum MessageRole { user, assistant }

/// Entité de domaine : ConversationMessage.
///
/// Représente un message échangé dans une conversation (texte ou vocale) avec W4FO.
class ConversationMessage extends Equatable {
  final MessageRole role;
  final String content;
  final DateTime timestamp;
  final bool isTranscribing;

  ConversationMessage({
    required this.role,
    required this.content,
    DateTime? timestamp,
    this.isTranscribing = false,
  }) : timestamp = timestamp ?? DateTime.now();

  /// Sérialise au format attendu par l'API backend (`{"role": ..., "content": ...}`).
  Map<String, String> toApiJson() => {'role': role == MessageRole.user ? 'user' : 'assistant', 'content': content};

  ConversationMessage copyWith({String? content, bool? isTranscribing}) {
    return ConversationMessage(
      role: role,
      content: content ?? this.content,
      timestamp: timestamp,
      isTranscribing: isTranscribing ?? this.isTranscribing,
    );
  }

  @override
  List<Object?> get props => [role, content, timestamp, isTranscribing];
}
