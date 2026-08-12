import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../models/user_model.dart';
import '../../../domain/entities/user.dart';

/// Résultat brut de connexion, avant persistance des tokens (responsabilité du repository).
class LoginTokens {
  final String accessToken;
  final String refreshToken;
  const LoginTokens({required this.accessToken, required this.refreshToken});
}

/// Datasource distante : appels HTTP bruts vers `/api/v1/auth`.
class AuthRemoteDataSource {
  final Dio _dio;

  const AuthRemoteDataSource(ApiClient apiClient) : _dio = apiClient.dio;

  Future<User> register({required String email, required String fullName, required String password}) async {
    final response = await _dio.post('/api/v1/auth/register', data: {
      'email': email,
      'full_name': fullName,
      'password': password,
    });
    return UserModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<LoginTokens> login({required String email, required String password}) async {
    final response = await _dio.post('/api/v1/auth/login', data: {'email': email, 'password': password});
    final data = response.data as Map<String, dynamic>;
    return LoginTokens(accessToken: data['access_token'] as String, refreshToken: data['refresh_token'] as String);
  }
}
