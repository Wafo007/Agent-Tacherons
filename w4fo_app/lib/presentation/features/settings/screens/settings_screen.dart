import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../application/providers/auth_provider.dart';
import '../../../../application/providers/background_listening_provider.dart';
import '../../../../application/providers/settings_provider.dart';
import '../../../../application/providers/whatsapp_provider.dart';
import '../../../../data/datasources/remote/settings_remote_datasource.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(settingsProvider);
    final settings = state.settings;

    return Scaffold(
      appBar: AppBar(title: const Text('Réglages')),
      body: state.isLoading || settings == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _SectionTitle('Voix & audio'),
                Card(
                  child: Column(
                    children: [
                      ListTile(
                        title: const Text('Voix de l\'assistant'),
                        subtitle: Text(settings.voiceId == 'male_fr' ? 'Voix masculine (Henri)' : 'Voix féminine (Denise)'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _showVoicePicker(context, ref, settings),
                      ),
                      const Divider(height: 1),
                      ListTile(
                        title: const Text('Volume'),
                        subtitle: Slider(
                          value: settings.volumeLevel.toDouble(),
                          min: 0,
                          max: 100,
                          divisions: 20,
                          label: '${settings.volumeLevel}%',
                          onChanged: (value) {
                            ref.read(settingsProvider.notifier).update(settings.copyWith(volumeLevel: value.round()));
                          },
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                _SectionTitle('Réveil intelligent'),
                Card(
                  child: ListTile(
                    title: const Text('Heure du briefing matinal'),
                    subtitle: Text(settings.briefingTime.substring(0, 5)),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _pickBriefingTime(context, ref, settings),
                  ),
                ),
                const SizedBox(height: 24),
                _SectionTitle('Écoute permanente (bêta)'),
                _BackgroundListeningCard(),
                const SizedBox(height: 24),
                _SectionTitle('WhatsApp (bêta)'),
                _WhatsAppCard(),
                const SizedBox(height: 24),
                _SectionTitle('Apparence'),
                Card(
                  child: SwitchListTile(
                    title: const Text('Mode sombre'),
                    value: settings.darkMode,
                    onChanged: (value) => ref.read(settingsProvider.notifier).update(settings.copyWith(darkMode: value)),
                  ),
                ),
                const SizedBox(height: 24),
                _SectionTitle('Autonomie de l\'assistant'),
                Card(
                  child: Column(
                    children: ['low', 'medium', 'high'].map((level) {
                      return RadioListTile<String>(
                        title: Text(_autonomyLabel(level)),
                        value: level,
                        groupValue: settings.autonomyLevel,
                        onChanged: (value) {
                          if (value != null) {
                            ref.read(settingsProvider.notifier).update(settings.copyWith(autonomyLevel: value));
                          }
                        },
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 24),
                OutlinedButton.icon(
                  onPressed: () => ref.read(authProvider.notifier).logout(),
                  icon: const Icon(Icons.logout),
                  label: const Text('Se déconnecter'),
                ),
              ],
            ),
    );
  }

  String _autonomyLabel(String level) {
    switch (level) {
      case 'low':
        return 'Faible — confirmation systématique avant toute action';
      case 'high':
        return 'Élevée — large autonomie, confirmation uniquement si critique';
      default:
        return 'Moyenne — confirmation pour les actions sensibles uniquement';
    }
  }

  void _showVoicePicker(BuildContext context, WidgetRef ref, UserSettingsData settings) {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: const Text('Voix féminine (Denise)'),
              onTap: () {
                ref.read(settingsProvider.notifier).update(settings.copyWith(voiceId: 'female_fr'));
                Navigator.of(context).pop();
              },
            ),
            ListTile(
              title: const Text('Voix masculine (Henri)'),
              onTap: () {
                ref.read(settingsProvider.notifier).update(settings.copyWith(voiceId: 'male_fr'));
                Navigator.of(context).pop();
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _pickBriefingTime(BuildContext context, WidgetRef ref, UserSettingsData settings) async {
    final parts = settings.briefingTime.split(':');
    final initial = TimeOfDay(hour: int.parse(parts[0]), minute: int.parse(parts[1]));
    final picked = await showTimePicker(context: context, initialTime: initial);
    if (picked == null) return;

    final formatted =
        '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}:00';
    ref.read(settingsProvider.notifier).update(settings.copyWith(briefingTime: formatted));
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, left: 4),
      child: Text(title, style: Theme.of(context).textTheme.titleSmall),
    );
  }
}

/// Carte de réglage pour l'écoute permanente ("Wafo") en arrière-plan
/// (§ ANDROID SERVICE). Affiche explicitement les limites du système
/// (notification obligatoire, dépendance à l'optimisation batterie) plutôt
/// que de présenter la fonctionnalité comme un "always-on" sans contrainte.
class _BackgroundListeningCard extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(backgroundListeningProvider);
    final notifier = ref.read(backgroundListeningProvider.notifier);

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: Column(
          children: [
            SwitchListTile(
              title: const Text('Écouter « Wafo » même app fermée'),
              subtitle: Text(
                state.starting
                    ? 'Activation en cours…'
                    : 'Affiche une notification persistante (obligatoire sur Android). '
                        "Peut s'arrêter si le système manque de mémoire ou si la batterie "
                        'est fortement optimisée par le fabricant du téléphone.',
              ),
              value: state.enabled,
              onChanged: state.starting
                  ? null
                  : (value) async {
                      if (value) {
                        await notifier.enable();
                      } else {
                        await notifier.disable();
                      }
                    },
            ),
            if (state.error != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Text(
                  state.error!,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (state.enabled) ...[
              const Divider(height: 1),
              ListTile(
                title: const Text('Optimisation de la batterie'),
                subtitle: const Text(
                  "Pour limiter les risques que le système coupe l'écoute, exclus W4FO "
                  "de l'optimisation de la batterie dans les réglages Android.",
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => notifier.openBatteryOptimizationSettings(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Carte de réglage pour la lecture/réponse WhatsApp on-device (§ WHATSAPP).
///
/// Explique explicitement le mécanisme (accès aux notifications + réponse
/// via l'action native de la notification) plutôt que de présenter ceci
/// comme une intégration Meta officielle — ce n'en est pas une (voir
/// `core/whatsapp/README.md`).
class _WhatsAppCard extends ConsumerStatefulWidget {
  @override
  ConsumerState<_WhatsAppCard> createState() => _WhatsAppCardState();
}

class _WhatsAppCardState extends ConsumerState<_WhatsAppCard> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(whatsAppProvider.notifier).refreshPermissionStatus();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState appState) {
    if (appState == AppLifecycleState.resumed) {
      // L'utilisateur revient probablement de l'écran système d'accès aux
      // notifications — on réévalue l'état réel plutôt que de supposer.
      ref.read(whatsAppProvider.notifier).refreshPermissionStatus();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(whatsAppProvider);
    final notifier = ref.read(whatsAppProvider.notifier);

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Text(
                "W4FO peut lire à voix haute tes messages WhatsApp reçus et y répondre à ta "
                "demande, directement depuis ton numéro personnel — sans passer par les serveurs "
                "de Meta. Ceci utilise l'action \"Répondre\" intégrée par WhatsApp à ses "
                "notifications, pas une intégration officielle Meta.",
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
            if (!state.hasNotificationAccess)
              ListTile(
                title: const Text("Autoriser l'accès aux notifications"),
                subtitle: const Text('Requis pour lire les messages WhatsApp reçus.'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => notifier.requestNotificationAccess(),
              )
            else
              SwitchListTile(
                title: const Text('Lire et répondre à mes messages WhatsApp'),
                subtitle: const Text(
                  'Dis "Wafo" après une annonce de message pour y répondre à voix haute.',
                ),
                value: state.listeningEnabled,
                onChanged: (value) async {
                  if (value) {
                    await notifier.enable();
                  } else {
                    await notifier.disable();
                  }
                },
              ),
            if (state.lastError != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Text(
                  state.lastError!,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.error),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
