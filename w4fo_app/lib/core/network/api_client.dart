import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../constants/app_constants.dart';
import '../errors/app_exceptions.dart';

/// Client HTTP centralisé pour tous les appels REST vers le backend W4FO.
///
/// Un seul point de configuration (base URL, timeouts, intercepteur JWT) :
/// les datasources ne créent jamais leur propre instance Dio.
class ApiClient {
  final Dio dio;
  final FlutterSecureStorage _secureStorage;

  ApiClient({FlutterSecureStorage? secureStorage})
      : _secureStorage = secureStorage ?? const FlutterSecureStorage(),
        dio = Dio(BaseOptions(
          baseUrl: AppConstants.apiBaseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
        )) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _secureStorage.read(key: AppConstants.secureStorageAccessTokenKey);
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (DioException error, handler) {
          handler.next(_mapError(error));
        },
      ),
    );
  }

  DioException _mapError(DioException error) {
    final statusCode = error.response?.statusCode;
    if (statusCode == 401) {
      return error.copyWith(error: const UnauthorizedException());
    }
    if (error.type == DioExceptionType.connectionError || error.type == DioExceptionType.connectionTimeout) {
      return error.copyWith(error: const NetworkException());
    }
    return error;
  }
}
