import '../entities/task.dart';

/// Interface (Port) : TaskRepository.
abstract class TaskRepository {
  Future<List<Task>> listTasks({TaskStatus? status, String? category});

  Future<Task> createTask({
    required String title,
    String description = '',
    DateTime? dueDate,
    TaskPriority priority = TaskPriority.medium,
    String category = 'general',
  });

  Future<Task> updateTask(String taskId, {String? title, TaskStatus? status, TaskPriority? priority});

  Future<void> deleteTask(String taskId);
}
