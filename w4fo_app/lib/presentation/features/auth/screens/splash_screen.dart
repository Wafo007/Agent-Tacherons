import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';

/// Écran affiché UNIQUEMENT pendant la restauration de session au démarrage
/// (`AuthStatus.unknown`, voir `app_router.dart` et `auth_provider.dart`).
///
/// Volontairement minimal et sans aucun appel API ni provider dépendant du
/// réseau : c'est précisément le but de cet écran d'éviter que du contenu
/// protégé (et les appels API qu'il déclenche) ne s'affiche avant que l'on
/// sache si la session est valide.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(colors: [AppColors.primary, AppColors.primaryDark]),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Icon(Icons.graphic_eq_rounded, color: Colors.white, size: 36),
              ),
              const SizedBox(height: 16),
              Text('W4FO', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 32),
              const SizedBox(
                width: 28,
                height: 28,
                child: CircularProgressIndicator(strokeWidth: 2.5, color: AppColors.primary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
