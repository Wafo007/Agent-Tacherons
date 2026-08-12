import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../application/providers/calendar_provider.dart';
import '../../../../core/theme/app_colors.dart';
import '../widgets/event_card.dart';

class CalendarScreen extends ConsumerWidget {
  const CalendarScreen({super.key});

  void _showCreateEventSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const _CreateEventSheet(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(calendarProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Mon agenda'),
        actions: [
          IconButton(
            icon: Icon(state.googleConnected ? Icons.cloud_done_rounded : Icons.cloud_off_rounded),
            tooltip: state.googleConnected ? 'Google Calendar connecté' : 'Connecter Google Calendar',
            onPressed: () {
              if (state.googleConnected) {
                ref.read(calendarProvider.notifier).disconnectGoogle();
              } else {
                _showGoogleConnectDialog(context, ref);
              }
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showCreateEventSheet(context),
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          if (state.lastConflicts.isNotEmpty) _ConflictBanner(conflicts: state.lastConflicts),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.read(calendarProvider.notifier).loadEvents(),
              child: state.isLoading && state.events.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : state.events.isEmpty
                      ? ListView(
                          padding: const EdgeInsets.all(32),
                          children: [
                            const SizedBox(height: 80),
                            Icon(Icons.event_available_rounded, size: 56, color: AppColors.darkOnSurfaceMuted),
                            const SizedBox(height: 16),
                            Text(
                              'Aucun événement à venir.',
                              textAlign: TextAlign.center,
                              style: Theme.of(context)
                                  .textTheme
                                  .bodyLarge
                                  ?.copyWith(color: AppColors.darkOnSurfaceMuted),
                            ),
                          ],
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: state.events.length,
                          itemBuilder: (context, index) {
                            final event = state.events[index];
                            return EventCard(
                              event: event,
                              onDelete: () => ref.read(calendarProvider.notifier).deleteEvent(event.id),
                            );
                          },
                        ),
            ),
          ),
        ],
      ),
    );
  }

  void _showGoogleConnectDialog(BuildContext context, WidgetRef ref) {
    // NOTE V2 : le flow OAuth complet (webview Google Sign-In) sera implémenté
    // avec le package `google_sign_in` ou une webview dédiée. Ce dialogue est
    // un point d'entrée temporaire tant que ce flow n'est pas branché.
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Connecter Google Calendar'),
        content: const Text(
          "Le flow de connexion Google (écran de consentement) n'est pas encore implémenté dans cette version. "
          "Voir le backend : POST /api/v1/calendar/connect/callback.",
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Fermer'))],
      ),
    );
  }
}

class _ConflictBanner extends StatelessWidget {
  final List<dynamic> conflicts;
  const _ConflictBanner({required this.conflicts});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppColors.warning.withOpacity(0.15), borderRadius: BorderRadius.circular(14)),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: AppColors.warning),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '${conflicts.length} conflit(s) détecté(s) avec un événement existant.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

class _CreateEventSheet extends ConsumerStatefulWidget {
  const _CreateEventSheet();

  @override
  ConsumerState<_CreateEventSheet> createState() => _CreateEventSheetState();
}

class _CreateEventSheetState extends ConsumerState<_CreateEventSheet> {
  final _titleController = TextEditingController();
  DateTime _startTime = DateTime.now().add(const Duration(hours: 1));
  DateTime _endTime = DateTime.now().add(const Duration(hours: 2));

  @override
  void dispose() {
    _titleController.dispose();
    super.dispose();
  }

  Future<void> _pickDateTime({required bool isStart}) async {
    final initial = isStart ? _startTime : _endTime;
    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (date == null || !mounted) return;

    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(initial));
    if (time == null) return;

    final combined = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    setState(() {
      if (isStart) {
        _startTime = combined;
      } else {
        _endTime = combined;
      }
    });
  }

  void _submit() {
    if (_titleController.text.trim().isEmpty) return;
    if (_endTime.isBefore(_startTime)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('La date de fin doit être après la date de début.')),
      );
      return;
    }
    ref.read(calendarProvider.notifier).createEvent(
          title: _titleController.text.trim(),
          startTime: _startTime,
          endTime: _endTime,
        );
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('dd/MM/yyyy HH:mm', 'fr_FR');

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Nouvel événement', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            TextField(
              controller: _titleController,
              autofocus: true,
              decoration: const InputDecoration(labelText: "Titre de l'événement"),
            ),
            const SizedBox(height: 16),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.play_arrow_rounded),
              title: const Text('Début'),
              subtitle: Text(dateFormat.format(_startTime)),
              onTap: () => _pickDateTime(isStart: true),
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.stop_rounded),
              title: const Text('Fin'),
              subtitle: Text(dateFormat.format(_endTime)),
              onTap: () => _pickDateTime(isStart: false),
            ),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _submit, child: const Text('Créer')),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
