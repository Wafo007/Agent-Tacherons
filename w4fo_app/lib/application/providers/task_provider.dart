import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/injection.dart';
import '../../domain/entities/task.dart';

class TaskListState {
  final List<Task> tasks;
  final bool isLoading;
  final String? errorMessage;

  const TaskListState({this.tasks = const [], this.isLoading = false, this.errorMessage});

  TaskListState copyWith({List<Task>? tasks, bool? isLoading, String? errorMessage}) {
    return TaskListState(
      tasks: tasks ?? this.tasks,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage,
    );
  }
}

/// Gère la liste des tâches de l'utilisateur : chargement, création, mise à
/// jour de statut, suppression — avec mise à jour optimiste de l'état local
/// pour une UI réactive sans attendre systématiquement l'aller-retour serveur.
class TaskListNotifier extends StateNotifier<TaskListState> {
  final Ref _ref;

  TaskListNotifier(this._ref) : super(const TaskListState()) {
    loadTasks();
  }

  Future<void> loadTasks() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final tasks = await _ref.read(taskRepositoryProvider).listTasks();
      state = state.copyWith(tasks: tasks, isLoading: false);
    } catch (_) {
      state = state.copyWith(isLoading: false, errorMessage: 'Impossible de charger les tâches.');
    }
  }

  Future<void> createTask({
    required String title,
    String description = '',
    DateTime? dueDate,
    TaskPriority priority = TaskPriority.medium,
    String category = 'general',
  }) async {
    try {
      final task = await _ref.read(taskRepositoryProvider).createTask(
            title: title,
            description: description,
            dueDate: dueDate,
            priority: priority,
            category: category,
          );
      state = state.copyWith(tasks: [...state.tasks, task]);
    } catch (_) {
      state = state.copyWith(errorMessage: 'Impossible de créer la tâche.');
    }
  }

  Future<void> markDone(String taskId) async {
    // Mise à jour optimiste : l'UI réagit immédiatement, sans attendre le serveur.
    final previousTasks = state.tasks;
    state = state.copyWith(
      tasks: state.tasks.map((t) => t.id == taskId ? t.copyWith(status: TaskStatus.done) : t).toList(),
    );
    try {
      await _ref.read(taskRepositoryProvider).updateTask(taskId, status: TaskStatus.done);
    } catch (_) {
      state = state.copyWith(tasks: previousTasks, errorMessage: 'Impossible de mettre à jour la tâche.');
    }
  }

  Future<void> deleteTask(String taskId) async {
    final previousTasks = state.tasks;
    state = state.copyWith(tasks: state.tasks.where((t) => t.id != taskId).toList());
    try {
      await _ref.read(taskRepositoryProvider).deleteTask(taskId);
    } catch (_) {
      state = state.copyWith(tasks: previousTasks, errorMessage: 'Impossible de supprimer la tâche.');
    }
  }
}

final taskListProvider = StateNotifierProvider<TaskListNotifier, TaskListState>((ref) => TaskListNotifier(ref));
