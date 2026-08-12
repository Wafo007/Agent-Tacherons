import '../../domain/entities/conversation_message.dart';
import '../../domain/repositories/conversation_repository.dart';
import '../datasources/remote/conversation_remote_datasource.dart';

class ConversationRepositoryImpl implements ConversationRepository {
  final ConversationRemoteDataSource _remoteDataSource;

  const ConversationRepositoryImpl(this._remoteDataSource);

  @override
  Future<ConversationResult> sendMessage(String content, List<ConversationMessage> history) {
    return _remoteDataSource.sendMessage(content, history);
  }
}
