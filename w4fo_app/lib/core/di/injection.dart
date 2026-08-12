import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/datasources/local/secure_storage.dart';
import '../../data/datasources/remote/auth_remote_datasource.dart';
import '../../data/datasources/remote/calendar_remote_datasource.dart';
import '../../data/datasources/remote/conversation_remote_datasource.dart';
import '../../data/datasources/remote/settings_remote_datasource.dart';
import '../../data/datasources/remote/task_remote_datasource.dart';
import '../../data/repositories_impl/auth_repository_impl.dart';
import '../../data/repositories_impl/calendar_repository_impl.dart';
import '../../data/repositories_impl/conversation_repository_impl.dart';
import '../../data/repositories_impl/settings_repository_impl.dart';
import '../../data/repositories_impl/task_repository_impl.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../domain/repositories/calendar_repository.dart';
import '../../domain/repositories/conversation_repository.dart';
import '../../domain/repositories/settings_repository.dart';
import '../../domain/repositories/task_repository.dart';
import '../network/api_client.dart';

/// Point de câblage unique de l'injection de dépendances (équivalent du
/// `dependencies.py` côté backend) : chaque interface de domaine est reliée
/// ici à son implémentation concrète. Les écrans et providers d'état ne
/// dépendent jamais directement d'une classe `*Impl` ou `*RemoteDataSource`.

final secureStorageProvider = Provider<SecureStorage>((ref) => const SecureStorage());

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final remote = AuthRemoteDataSource(ref.watch(apiClientProvider));
  return AuthRepositoryImpl(remote, ref.watch(secureStorageProvider));
});

final taskRepositoryProvider = Provider<TaskRepository>((ref) {
  final remote = TaskRemoteDataSource(ref.watch(apiClientProvider));
  return TaskRepositoryImpl(remote);
});

final conversationRepositoryProvider = Provider<ConversationRepository>((ref) {
  final remote = ConversationRemoteDataSource(ref.watch(apiClientProvider));
  return ConversationRepositoryImpl(remote);
});

final calendarRepositoryProvider = Provider<CalendarRepository>((ref) {
  final remote = CalendarRemoteDataSource(ref.watch(apiClientProvider));
  return CalendarRepositoryImpl(remote);
});

final settingsRepositoryProvider = Provider<SettingsRepository>((ref) {
  final remote = SettingsRemoteDataSource(ref.watch(apiClientProvider));
  return SettingsRepositoryImpl(remote);
});
