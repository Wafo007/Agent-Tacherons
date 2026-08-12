import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../../domain/entities/conversation_message.dart';
import '../../../domain/repositories/conversation_repository.dart';

/// Datasource distante : appels HTTP bruts vers `/api/v1/conversation/message`.
class ConversationRemoteDataSource {
  final Dio _dio;

  const ConversationRemoteDataSource(ApiClient apiClient) : _dio = apiClient.dio;

  Future<ConversationResult> sendMessage(String content, List<ConversationMessage> history) async {
    final response = await _dio.post('/api/v1/conversation/message', data: {
      'content': content,
      'history': history.map((m) => m.toApiJson()).toList(),
    });
    final data = response.data as Map<String, dynamic>;
    return ConversationResult(
      response: data['response'] as String? ?? '',
      requiresConfirmation: data['requires_confirmation'] as bool? ?? false,
      pendingToolCall: data['pending_tool_call'] as Map<String, dynamic>?,
    );
  }
}
