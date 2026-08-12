import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../application/providers/task_provider.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../domain/entities/task.dart';
import '../widgets/task_card.dart';

class TasksScreen extends ConsumerWidget {
  const TasksScreen({super.key});

  void _showCreateTaskSheet(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const _CreateTaskSheet(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(taskListProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Mes tâches')),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showCreateTaskSheet(context, ref),
        child: const Icon(Icons.add),
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(taskListProvider.notifier).loadTasks(),
        child: state.isLoading && state.tasks.isEmpty
            ? const Center(child: CircularProgressIndicator())
            : state.tasks.isEmpty
                ? ListView(
                    padding: const EdgeInsets.all(32),
                    children: [
                      const SizedBox(height: 80),
                      Icon(Icons.checklist_rounded, size: 56, color: AppColors.darkOnSurfaceMuted),
                      const SizedBox(height: 16),
                      Text(
                        'Aucune tâche pour le moment.\nDemande à W4FO ou appuie sur + pour en créer une.',
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
                    itemCount: state.tasks.length,
                    itemBuilder: (context, index) {
                      final task = state.tasks[index];
                      return TaskCard(
                        task: task,
                        onMarkDone: () => ref.read(taskListProvider.notifier).markDone(task.id),
                        onDelete: () => ref.read(taskListProvider.notifier).deleteTask(task.id),
                      );
                    },
                  ),
      ),
    );
  }
}

class _CreateTaskSheet extends ConsumerStatefulWidget {
  const _CreateTaskSheet();

  @override
  ConsumerState<_CreateTaskSheet> createState() => _CreateTaskSheetState();
}

class _CreateTaskSheetState extends ConsumerState<_CreateTaskSheet> {
  final _titleController = TextEditingController();
  TaskPriority _priority = TaskPriority.medium;

  @override
  void dispose() {
    _titleController.dispose();
    super.dispose();
  }

  void _submit() {
    if (_titleController.text.trim().isEmpty) return;
    ref.read(taskListProvider.notifier).createTask(title: _titleController.text.trim(), priority: _priority);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
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
            Text('Nouvelle tâche', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            TextField(
              controller: _titleController,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Titre de la tâche'),
              onSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              children: TaskPriority.values.map((p) {
                final selected = p == _priority;
                return ChoiceChip(
                  label: Text(p.apiValue),
                  selected: selected,
                  onSelected: (_) => setState(() => _priority = p),
                );
              }).toList(),
            ),
            const SizedBox(height: 24),
            ElevatedButton(onPressed: _submit, child: const Text('Créer')),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
