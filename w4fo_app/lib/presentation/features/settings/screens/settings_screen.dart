import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../application/providers/auth_provider.dart';
import '../../../../application/providers/settings_provider.dart';
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
