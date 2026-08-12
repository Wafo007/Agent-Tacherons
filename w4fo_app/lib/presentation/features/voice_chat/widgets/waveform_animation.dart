import 'dart:math';

import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';

/// Animation d'ondes sonores affichée pendant la phase d'écoute (`listening`).
/// Purement décorative (pas connectée au volume réel du micro dans cette V1) —
/// une évolution future pourrait la piloter avec l'amplitude réelle renvoyée
/// par `record`'s `onAmplitudeChanged`.
class WaveformAnimation extends StatefulWidget {
  final bool isActive;

  const WaveformAnimation({super.key, required this.isActive});

  @override
  State<WaveformAnimation> createState() => _WaveformAnimationState();
}

class _WaveformAnimationState extends State<WaveformAnimation> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  final _random = Random();
  late final List<double> _barSeeds;

  @override
  void initState() {
    super.initState();
    _barSeeds = List.generate(5, (_) => _random.nextDouble());
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.isActive) {
      return const SizedBox(height: 32);
    }

    return SizedBox(
      height: 32,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(5, (index) {
              final phase = _barSeeds[index];
              final t = (_controller.value + phase) % 1.0;
              final height = 8 + (sin(t * pi) * 24).abs();
              return Container(
                margin: const EdgeInsets.symmetric(horizontal: 3),
                width: 4,
                height: height,
                decoration: BoxDecoration(color: AppColors.accent, borderRadius: BorderRadius.circular(2)),
              );
            }),
          );
        },
      ),
    );
  }
}
