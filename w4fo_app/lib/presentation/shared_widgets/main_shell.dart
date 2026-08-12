import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/router/app_router.dart';

/// Structure de navigation principale : barre de navigation inférieure
/// commune à tous les écrans internes (voix, tâches, agenda, paramètres).
class MainShell extends StatelessWidget {
  final Widget child;

  const MainShell({super.key, required this.child});

  int _indexForLocation(String location) {
    switch (location) {
      case AppRoutes.tasks:
        return 1;
      case AppRoutes.calendar:
        return 2;
      case AppRoutes.settings:
        return 3;
      default:
        return 0;
    }
  }

  void _onTap(BuildContext context, int index) {
    switch (index) {
      case 0:
        context.go(AppRoutes.home);
      case 1:
        context.go(AppRoutes.tasks);
      case 2:
        context.go(AppRoutes.calendar);
      case 3:
        context.go(AppRoutes.settings);
    }
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    final currentIndex = _indexForLocation(location);

    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: currentIndex,
        onDestinationSelected: (index) => _onTap(context, index),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.mic_none_rounded), selectedIcon: Icon(Icons.mic_rounded), label: 'W4FO'),
          NavigationDestination(icon: Icon(Icons.checklist_rounded), label: 'Tâches'),
          NavigationDestination(icon: Icon(Icons.calendar_month_rounded), label: 'Agenda'),
          NavigationDestination(icon: Icon(Icons.settings_rounded), label: 'Réglages'),
        ],
      ),
    );
  }
}
