import 'package:flutter/material.dart';

/// Palette de couleurs W4FO — identité visuelle distincte plutôt que les
/// bleus/violets par défaut de Material 3, cohérente avec un assistant IA
/// personnel "chaleureux mais technique".
class AppColors {
  // Teinte principale : indigo profond, évoque la confiance et la technologie
  // sans tomber dans le violet générique "startup IA".
  static const Color primary = Color(0xFF3D5AFE);
  static const Color primaryDark = Color(0xFF2942D6);

  // Accent chaud pour les actions vocales (micro actif, ondes sonores)
  static const Color accent = Color(0xFFFF7A45);

  static const Color success = Color(0xFF2ECC71);
  static const Color warning = Color(0xFFF5A623);
  static const Color danger = Color(0xFFE74C3C);

  // Thème sombre (par défaut, cohérent avec §2 du document d'architecture)
  static const Color darkBackground = Color(0xFF10131A);
  static const Color darkSurface = Color(0xFF1A1E29);
  static const Color darkSurfaceVariant = Color(0xFF232838);
  static const Color darkOnSurface = Color(0xFFE8EAF0);
  static const Color darkOnSurfaceMuted = Color(0xFF8B92A8);

  // Thème clair
  static const Color lightBackground = Color(0xFFF7F8FC);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightOnSurface = Color(0xFF1A1E29);
  static const Color lightOnSurfaceMuted = Color(0xFF6B7280);
}
