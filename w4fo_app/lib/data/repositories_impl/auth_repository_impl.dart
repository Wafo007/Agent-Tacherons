import '../../domain/entities/user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/local/secure_storage.dart';
import '../datasources/remote/auth_remote_datasource.dart';

class AuthRepositoryImpl implements AuthRepository {
  final AuthRemoteDataSource _remoteDataSource;
  final SecureStorage _secureStorage;

  const AuthRepositoryImpl(this._remoteDataSource, this._secureStorage);

  @override
  Future<User> register({required String email, required String fullName, required String password}) {
    return _remoteDataSource.register(email: email, fullName: fullName, password: password);
  }

  @override
  Future<void> login({required String email, required String password}) async {
    final tokens = await _remoteDataSource.login(email: email, password: password);
    await _secureStorage.saveTokens(accessToken: tokens.accessToken, refreshToken: tokens.refreshToken);
  }

  @override
  Future<void> logout() => _secureStorage.clear();

  @override
  Future<String?> getAccessToken() => _secureStorage.getAccessToken();

  @override
  Future<bool> isLoggedIn() async => (await _secureStorage.getAccessToken()) != null;
}
