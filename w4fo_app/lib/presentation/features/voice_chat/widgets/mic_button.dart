import 'package:flutter/material.dart';

import '../../../../application/state/voice_chat_state.dart';
import '../../../../core/theme/app_colors.dart';

/// Bouton micro central de l'écran de conversation vocale. Son apparence
/// (couleur, icône, pulsation) reflète directement `VoiceChatPhase`, pour que
/// l'utilisateur comprenne toujours en un coup d'œil ce que fait l'assistant.
class MicButton extends StatelessWidget {
  final VoiceChatPhase phase;
  final VoidCallback onTapStart;
  final VoidCallback onTapStop;

  const MicButton({
    super.key,
    required this.phase,
    required this.onTapStart,
    required this.onTapStop,
  });

  Color get _color {
    switch (phase) {
      case VoiceChatPhase.listening:
        return AppColors.accent;
      case VoiceChatPhase.thinking:
        return AppColors.warning;
      case VoiceChatPhase.speaking:
        return AppColors.success;
      case VoiceChatPhase.error:
        return AppColors.danger;
      default:
        return AppColors.primary;
    }
  }

  IconData get _icon {
    switch (phase) {
      case VoiceChatPhase.listening:
        return Icons.mic_rounded;
      case VoiceChatPhase.thinking:
        return Icons.psychology_outlined;
      case VoiceChatPhase.speaking:
        return Icons.volume_up_rounded;
      case VoiceChatPhase.awaitingConfirmation:
        return Icons.help_outline_rounded;
      case VoiceChatPhase.error:
        return Icons.error_outline_rounded;
      default:
        return Icons.mic_none_rounded;
    }
  }

  bool get _isBusy => phase == VoiceChatPhase.thinking || phase == VoiceChatPhase.speaking;

  @override
  Widget build(BuildContext context) {
    final isListening = phase == VoiceChatPhase.listening;

    return GestureDetector(
      onTap: _isBusy
          ? null
          : () => isListening ? onTapStop() : onTapStart(),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        width: isListening ? 108 : 96,
        height: isListening ? 108 : 96,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: _color,
          boxShadow: [
            BoxShadow(color: _color.withOpacity(0.35), blurRadius: 24, spreadRadius: isListening ? 8 : 2),
          ],
        ),
        child: Icon(_icon, color: Colors.white, size: 40),
      ),
    );
  }
}
