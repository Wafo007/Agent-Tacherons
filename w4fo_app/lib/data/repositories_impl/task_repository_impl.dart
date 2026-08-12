import '../../domain/entities/task.dart';
import '../../domain/repositories/task_repository.dart';
import '../datasources/remote/task_remote_datasource.dart';

class TaskRepositoryImpl implements TaskRepository {
  final TaskRemoteDataSource _remoteDataSource;

  const TaskRepositoryImpl(this._remoteDataSource);

  @override
  Future<List<Task>> listTasks({TaskStatus? status, String? category}) {
    return _remoteDataSource.listTasks(status: status, category: category);
  }

  @override
  Future<Task> createTask({
    required String title,
    String description = '',
    DateTime? dueDate,
    TaskPriority priority = TaskPriority.medium,
    String category = 'general',
  }) {
    return _remoteDataSource.createTask(
      title: title,
      description: description,
      dueDate: dueDate,
      priority: priority,
      category: category,
    );
  }

  @override
  Future<Task> updateTask(String taskId, {String? title, TaskStatus? status, TaskPriority? priority}) {
    return _remoteDataSource.updateTask(taskId, title: title, status: status, priority: priority);
  }

  @override
  Future<void> deleteTask(String taskId) => _remoteDataSource.deleteTask(taskId);
}
