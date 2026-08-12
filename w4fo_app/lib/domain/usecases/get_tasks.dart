import '../entities/task.dart';
import '../repositories/task_repository.dart';

/// Use case : récupère les tâches de l'utilisateur, avec filtres optionnels.
class GetTasks {
  final TaskRepository _repository;

  const GetTasks(this._repository);

  Future<List<Task>> call({TaskStatus? status, String? category}) {
    return _repository.listTasks(status: status, category: category);
  }
}
