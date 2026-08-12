import '../../domain/entities/task.dart';

/// Modèle de données pour Task : gère la sérialisation/désérialisation JSON
/// vers/depuis l'API backend. Convertit vers/depuis l'entité de domaine pure
/// `Task`, qui ne connaît rien du format JSON.
class TaskModel {
  static Task fromJson(Map<String, dynamic> json) {
    return Task(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String? ?? '',
      dueDate: json['due_date'] != null ? DateTime.parse(json['due_date'] as String) : null,
      priority: TaskPriorityX.fromApi(json['priority'] as String? ?? 'medium'),
      status: TaskStatusX.fromApi(json['status'] as String? ?? 'todo'),
      category: json['category'] as String? ?? 'general',
    );
  }

  static Map<String, dynamic> toCreateJson({
    required String title,
    required String description,
    DateTime? dueDate,
    required TaskPriority priority,
    required String category,
  }) {
    return {
      'title': title,
      'description': description,
      if (dueDate != null) 'due_date': dueDate.toIso8601String(),
      'priority': priority.apiValue,
      'category': category,
    };
  }

  static Map<String, dynamic> toUpdateJson({String? title, TaskStatus? status, TaskPriority? priority}) {
    return {
      if (title != null) 'title': title,
      if (status != null) 'status': status.apiValue,
      if (priority != null) 'priority': priority.apiValue,
    };
  }
}
