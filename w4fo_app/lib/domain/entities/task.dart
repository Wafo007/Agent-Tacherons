import 'package:equatable/equatable.dart';

/// Niveaux de priorité d'une tâche, alignés sur le domaine backend
/// (`src/domain/value_objects/priority.py`).
enum TaskPriority { low, medium, high, urgent }

/// Statuts possibles d'une tâche, alignés sur le domaine backend.
enum TaskStatus { todo, inProgress, done, cancelled, postponed }

extension TaskPriorityX on TaskPriority {
  String get apiValue => name;

  static TaskPriority fromApi(String value) =>
      TaskPriority.values.firstWhere((p) => p.apiValue == value, orElse: () => TaskPriority.medium);
}

extension TaskStatusX on TaskStatus {
  /// Le backend utilise `in_progress` (snake_case) alors que Dart utilise `inProgress` (camelCase).
  String get apiValue {
    switch (this) {
      case TaskStatus.inProgress:
        return 'in_progress';
      default:
        return name;
    }
  }

  static TaskStatus fromApi(String value) {
    switch (value) {
      case 'in_progress':
        return TaskStatus.inProgress;
      default:
        return TaskStatus.values.firstWhere((s) => s.name == value, orElse: () => TaskStatus.todo);
    }
  }
}

/// Entité de domaine : Task.
///
/// Représente une tâche telle que manipulée par l'application, indépendamment
/// de la façon dont elle est sérialisée/désérialisée pour l'API (voir
/// `data/models/task_model.dart` pour le mapping JSON).
class Task extends Equatable {
  final String id;
  final String title;
  final String description;
  final DateTime? dueDate;
  final TaskPriority priority;
  final TaskStatus status;
  final String category;

  const Task({
    required this.id,
    required this.title,
    this.description = '',
    this.dueDate,
    this.priority = TaskPriority.medium,
    this.status = TaskStatus.todo,
    this.category = 'general',
  });

  Task copyWith({
    String? title,
    String? description,
    DateTime? dueDate,
    TaskPriority? priority,
    TaskStatus? status,
    String? category,
  }) {
    return Task(
      id: id,
      title: title ?? this.title,
      description: description ?? this.description,
      dueDate: dueDate ?? this.dueDate,
      priority: priority ?? this.priority,
      status: status ?? this.status,
      category: category ?? this.category,
    );
  }

  bool get isOverdue =>
      dueDate != null && dueDate!.isBefore(DateTime.now()) && status != TaskStatus.done && status != TaskStatus.cancelled;

  @override
  List<Object?> get props => [id, title, description, dueDate, priority, status, category];
}
