import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../application/providers/background_listening_provider.dart';
import '../../../../application/providers/voice_chat_provider.dart';
import '../../../../application/state/voice_chat_state.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/voice/wafo_wake_word_detector.dart';
import '../../../../domain/entities/conversation_message.dart';
import '../widgets/mic_button.dart';
import '../widgets/waveform_animation.dart';

class VoiceChatScreen extends ConsumerStatefulWidget {
  const VoiceChatScreen({super.key});

  @override
  ConsumerState<VoiceChatScreen> createState() => _VoiceChatScreenState();
}

class _VoiceChatScreenState extends ConsumerState<VoiceChatScreen> with WidgetsBindingObserver {
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Connexion WebSocket différée après le premier frame pour éviter tout
    // appel réseau pendant la construction du widget.
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await ref.read(voiceChatProvider.notifier).connect();
      // Active l'écoute passive du Wake Word ("Wafo") au premier plan, SAUF
      // si le Foreground Service d'écoute permanente (§ ANDROID SERVICE) est
      // déjà actif : dans ce cas, c'est lui qui écoute (via le moteur
      // headless), et démarrer une seconde session ici entrerait en conflit
      // pour l'accès au micro. Traitement 100% local dans les deux cas (voir
      // WafoWakeWordDetector) : aucune donnée n'est envoyée à Mistral tant
      // que le mot-clé n'a pas été reconnu.
      final backgroundServiceActive = ref.read(backgroundListeningProvider).enabled;
      if (mounted && !backgroundServiceActive) {
        await ref.read(voiceChatProvider.notifier).enableWakeWord(WafoWakeWordDetector());
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState appState) {
    final notifier = ref.read(voiceChatProvider.notifier);
    switch (appState) {
      case AppLifecycleState.resumed:
        notifier.resumeWakeWordFromBackground();
      case AppLifecycleState.inactive:
      case AppLifecycleState.paused:
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
        // Respecte les restrictions Android modernes sur l'accès micro en
        // arrière-plan : on met l'écoute passive en pause plutôt que de
        // maintenir une session inutile (et coûteuse) hors premier plan.
        notifier.pauseWakeWordForBackground();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (!_scrollController.hasClients) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
  }

  String _phaseLabel(VoiceChatPhase phase, {required bool wakeWordActive}) {
    switch (phase) {
      case VoiceChatPhase.listening:
        return "Je t'écoute...";
      case VoiceChatPhase.transcribing:
        return 'Transcription en cours...';
      case VoiceChatPhase.thinking:
        return 'Je réfléchis...';
      case VoiceChatPhase.speaking:
        return 'Je réponds...';
      case VoiceChatPhase.awaitingConfirmation:
        return 'En attente de ta confirmation';
      case VoiceChatPhase.error:
        return 'Une erreur est survenue';
      case VoiceChatPhase.idle:
        // Cycle Wake Word : en attente, dis "Wafo" pour activer W4FO sans
        // toucher l'écran (voir core/voice/wafo_wake_word_detector.dart).
        return wakeWordActive ? 'Dis « Wafo » pour me parler' : 'Appuie pour parler';
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(voiceChatProvider);

    ref.listen(voiceChatProvider, (previous, next) {
      if (previous?.messages.length != next.messages.length) {
        _scrollToBottom();
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('W4FO')),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: state.messages.isEmpty
                  ? _EmptyState(phaseLabel: _phaseLabel(state.phase, wakeWordActive: state.wakeWordActive))
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      itemCount: state.messages.length,
                      itemBuilder: (context, index) => _MessageBubble(message: state.messages[index]),
                    ),
            ),
            if (state.phase == VoiceChatPhase.awaitingConfirmation) _ConfirmationBanner(toolCall: state.pendingToolCall),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Column(
                children: [
                  WaveformAnimation(isActive: state.phase == VoiceChatPhase.listening),
                  const SizedBox(height: 12),
                  Text(
                    _phaseLabel(state.phase, wakeWordActive: state.wakeWordActive),
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 20),
                  MicButton(
                    phase: state.phase,
                    onTapStart: () => ref.read(voiceChatProvider.notifier).startListening(),
                    onTapStop: () => ref.read(voiceChatProvider.notifier).stopListening(),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final String phaseLabel;
  const _EmptyState({required this.phaseLabel});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.graphic_eq_rounded, size: 56, color: AppColors.darkOnSurfaceMuted),
            const SizedBox(height: 16),
            Text(
              'Parle-moi de tes tâches, de ton agenda, ou demande-moi simplement comment ça va.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: AppColors.darkOnSurfaceMuted),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final ConversationMessage message;
  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == MessageRole.user;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
        decoration: BoxDecoration(
          color: isUser ? AppColors.primary : AppColors.darkSurfaceVariant,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Text(message.content, style: const TextStyle(color: Colors.white)),
      ),
    );
  }
}

class _ConfirmationBanner extends ConsumerWidget {
  final Map<String, dynamic>? toolCall;
  const _ConfirmationBanner({required this.toolCall});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppColors.warning.withOpacity(0.15), borderRadius: BorderRadius.circular(14)),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: AppColors.warning),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              "Cette action nécessite ta confirmation : dis « oui, confirme » ou « non, annule ».",
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}
