import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../application/providers/auth_provider.dart';
import '../../presentation/features/auth/screens/login_screen.dart';
import '../../presentation/features/auth/screens/register_screen.dart';
import '../../presentation/features/calendar/screens/calendar_screen.dart';
import '../../presentation/features/settings/screens/settings_screen.dart';
import '../../presentation/features/tasks/screens/tasks_screen.dart';
import '../../presentation/features/voice_chat/screens/voice_chat_screen.dart';
import '../../presentation/shared_widgets/main_shell.dart';

/// Routes nommées de l'application, centralisées pour éviter les chaînes
/// magiques dispersées dans les écrans.
abstract class AppRoutes {
  static const login = '/login';
  static const register = '/register';
  static const home = '/';
  static const tasks = '/tasks';
  static const calendar = '/calendar';
  static const settings = '/settings';
}

/// Provider Riverpod exposant une instance UNIQUE et stable du router.
///
/// Important : ne jamais appeler `buildAppRouter` directement dans `build()`
/// d'un widget — cela recréerait le GoRouter (et perdrait son historique de
/// navigation) à chaque rebuild. Toujours passer par ce provider.
final routerProvider = Provider<GoRouter>((ref) => buildAppRouter(ref));

/// Construit le router applicatif, avec redirection automatique selon l'état
/// d'authentification (§ProactivitéUX : jamais laisser un utilisateur non
/// connecté accéder aux écrans internes, ni un utilisateur connecté rester
/// bloqué sur l'écran de login).
GoRouter buildAppRouter(Ref ref) {
  return GoRouter(
    initialLocation: AppRoutes.home,
    refreshListenable: _AuthChangeNotifier(ref),
    redirect: (context, state) {
      final authState = ref.read(authProvider);
      final isLoggingRoute = state.matchedLocation == AppRoutes.login || state.matchedLocation == AppRoutes.register;

      if (authState.status == AuthStatus.unknown) return null; // Attend la résolution initiale

      if (authState.status == AuthStatus.unauthenticated && !isLoggingRoute) {
        return AppRoutes.login;
      }
      if (authState.status == AuthStatus.authenticated && isLoggingRoute) {
        return AppRoutes.home;
      }
      return null;
    },
    routes: [
      GoRoute(path: AppRoutes.login, builder: (context, state) => const LoginScreen()),
      GoRoute(path: AppRoutes.register, builder: (context, state) => const RegisterScreen()),
      ShellRoute(
        builder: (context, state, child) => MainShell(child: child),
        routes: [
          GoRoute(path: AppRoutes.home, builder: (context, state) => const VoiceChatScreen()),
          GoRoute(path: AppRoutes.tasks, builder: (context, state) => const TasksScreen()),
          GoRoute(path: AppRoutes.calendar, builder: (context, state) => const CalendarScreen()),
          GoRoute(path: AppRoutes.settings, builder: (context, state) => const SettingsScreen()),
        ],
      ),
    ],
  );
}

/// Pont entre Riverpod (StateNotifier) et `Listenable` (attendu par go_router
/// pour déclencher une réévaluation de `redirect` à chaque changement d'état).
class _AuthChangeNotifier extends ChangeNotifier {
  _AuthChangeNotifier(Ref ref) {
    ref.listen(authProvider, (_, __) => notifyListeners());
  }
}
