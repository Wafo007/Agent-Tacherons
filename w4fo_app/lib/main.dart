import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'application/providers/auth_provider.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

/// Point d'entrée de l'application W4FO.
///
/// L'URL du backend (`AppConstants.apiBaseUrl` / `wsBaseUrl`) est configurable
/// via `--dart-define=API_BASE_URL=... --dart-define=WS_BASE_URL=...` au build,
/// pour ne jamais coder en dur l'adresse du serveur de production dans le code
/// source (voir `core/constants/app_constants.dart`).
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Nécessaire pour que `DateFormat(..., 'fr_FR')` fonctionne (écrans Agenda/Tâches).
  await initializeDateFormatting('fr_FR', null);

  runApp(const ProviderScope(child: W4FOApp()));
}

class W4FOApp extends ConsumerStatefulWidget {
  const W4FOApp({super.key});

  @override
  ConsumerState<W4FOApp> createState() => _W4FOAppState();
}

/// `WidgetsBindingObserver` : détecte le retour de l'application au premier
/// plan (`AppLifecycleState.resumed`) pour revalider proactivement la session
/// (voir `AuthNotifier.revalidateOnResume`) — couvre le scénario "mise en
/// arrière-plan puis retour plusieurs heures plus tard" quand le processus de
/// l'app a survécu (pas de redémarrage complet). Le cas où l'OS a totalement
/// tué le processus est déjà couvert par la restauration au démarrage
/// (`AuthNotifier._checkInitialAuthStatus`, appelée depuis `main()` via le
/// constructeur de `AuthNotifier`), puisque `main()` est ré-exécuté.
class _W4FOAppState extends ConsumerState<W4FOApp> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      ref.read(authProvider.notifier).revalidateOnResume();
    }
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'W4FO',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.dark, // Mode sombre par défaut (§2 du document d'architecture)
      routerConfig: router,
    );
  }
}
